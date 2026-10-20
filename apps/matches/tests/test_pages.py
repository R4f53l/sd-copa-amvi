from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.championships.models import (
    Championship,
    ChampionshipTeam,
    PlayerRegistration,
)
from apps.matches import services
from apps.matches.models import EventType, Lineup, Match, MatchEvent
from apps.teams.models import City, Player, Team

User = get_user_model()
PLAYERS_PER_TEAM = 15


def aware(*args):
    return timezone.make_aware(datetime(*args))


class MatchPagesTestCase(TestCase):
    """Small, explicit fixture: one championship, two teams, one match."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "adm", password="x", role=User.Role.ADMIN
        )
        cls.official = User.objects.create_user("mesario", password="x")
        cls.other_official = User.objects.create_user("outro", password="x")

        city = City.objects.create(name="Picos", slug="picos")
        cls.championship = Championship.objects.create(
            name="Copa AMVI",
            season=2026,
            slug="copa-2026",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 15),
        )
        cls.home = cls._enroll(cls.championship, "Picos EC", "PIC", city)
        cls.away = cls._enroll(cls.championship, "Jaicos FC", "JAI", city)

        other = Championship.objects.create(
            name="Outra Copa", season=2026, slug="outra-2026"
        )
        cls.foreign_team = cls._enroll(other, "Oeiras FC", "OEI", city)

        cls.match = Match.objects.create(
            championship=cls.championship,
            home_team=cls.home,
            away_team=cls.away,
            round_number=1,
            scheduled_at=aware(2026, 10, 20, 16, 0),
        )
        cls.match.table_officials.add(cls.official)

    @staticmethod
    def _enroll(championship, name, short, city):
        team = Team.objects.create(
            name=name,
            short_name=short,
            slug=name.lower().replace(" ", "-"),
            city=city,
        )
        entry = ChampionshipTeam.objects.create(
            championship=championship, team=team
        )
        for number in range(1, PLAYERS_PER_TEAM + 1):
            player = Player.objects.create(
                full_name=f"{short} Jogador {number}"
            )
            PlayerRegistration.objects.create(
                championship_team=entry,
                player=player,
                shirt_number=number,
                registered_on=date(2026, 9, 1),
            )
        return entry

    def login(self, user):
        self.client.force_login(user)

    # helpers -------------------------------------------------------------

    def lineup_post_data(self, team, starters=11, subs=3, captain=1, **over):
        """
        Formset payload: the first ``starters`` players start, the next
        ``subs`` are substitutes, the rest are not listed.
        ``over`` maps a form index to field overrides.
        """
        candidates = list(services.lineup_candidates(self.match, team))
        data = {
            "form-TOTAL_FORMS": str(len(candidates)),
            "form-INITIAL_FORMS": str(len(candidates)),
        }
        for i, registration in enumerate(candidates):
            if i < starters:
                role = Lineup.Role.STARTER
            elif i < starters + subs:
                role = Lineup.Role.SUBSTITUTE
            else:
                role = ""
            fields = {
                "registration_id": str(registration.pk),
                "role": role,
                "shirt_number": str(registration.shirt_number),
                "position": "",
            }
            if i + 1 == captain and role:
                fields["is_captain"] = "on"
            fields.update(over.get(i, {}))
            for key, value in fields.items():
                if value is not None:
                    data[f"form-{i}-{key}"] = value
        return data

    def set_lineups(self):
        for team in (self.home, self.away):
            services.save_lineup(
                self.match,
                team,
                [
                    {
                        "registration": reg,
                        "role": (
                            Lineup.Role.STARTER
                            if i < 11
                            else Lineup.Role.SUBSTITUTE
                        ),
                        "shirt_number": reg.shirt_number,
                        "position": "",
                        "is_captain": i == 0,
                    }
                    for i, reg in enumerate(
                        services.lineup_candidates(self.match, team)[:14]
                    )
                ],
            )

    def lineup_of(self, team, shirt_number):
        return self.match.lineups.get(team=team, shirt_number=shirt_number)

    def post_event(self, code, team=None, **fields):
        data = {
            "event_type": code,
            "period": "1",
            "minute": "10",
            "stoppage_minute": "0",
        }
        if team is not None:
            data["team"] = str(team.pk)
        for role, lineup in fields.items():
            data[f"role_{role.replace('_', '-')}"] = str(lineup.pk)
        return self.client.post(
            reverse("matches:sheet", args=[self.match.pk]), data
        )


class PermissionTests(MatchPagesTestCase):
    def test_anonymous_is_redirected_to_login(self):
        for url in (
            reverse("matches:panel"),
            reverse("matches:sheet", args=[self.match.pk]),
        ):
            response = self.client.get(url)
            self.assertRedirects(
                response, f"{reverse('accounts:login')}?next={url}"
            )

    def test_assigned_official_can_run_the_match_sheet(self):
        self.login(self.official)
        for name, args in (
            ("matches:sheet", [self.match.pk]),
            ("matches:lineup", [self.match.pk, "home"]),
        ):
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 200)

    def test_unassigned_official_is_forbidden(self):
        self.login(self.other_official)
        response = self.client.get(
            reverse("matches:sheet", args=[self.match.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_only_admins_schedule_matches(self):
        self.login(self.official)
        create = reverse("matches:create", args=[self.championship.pk])
        update = reverse("matches:update", args=[self.match.pk])
        self.assertEqual(self.client.get(create).status_code, 403)
        self.assertEqual(self.client.get(update).status_code, 403)

    def test_officials_only_see_their_matches(self):
        self.login(self.other_official)
        response = self.client.get(reverse("matches:panel"))
        self.assertEqual(list(response.context["matches"]), [])

        self.login(self.official)
        response = self.client.get(reverse("matches:panel"))
        self.assertEqual(list(response.context["matches"]), [self.match])


class MatchFormTests(MatchPagesTestCase):
    def setUp(self):
        self.login(self.admin)
        self.url = reverse("matches:create", args=[self.championship.pk])

    def payload(self, **over):
        data = {
            "home_team": str(self.home.pk),
            "away_team": str(self.away.pk),
            "stage": Match.Stage.GROUP,
            "round_number": "2",
            "scheduled_at": "2026-10-27T16:00",
        }
        data.update(over)
        return data

    def test_create_match(self):
        response = self.client.post(self.url, self.payload())
        match = Match.objects.get(round_number=2)
        self.assertRedirects(
            response, reverse("matches:sheet", args=[match.pk])
        )
        self.assertEqual(match.championship, self.championship)
        self.assertEqual(match.status, Match.Status.SCHEDULED)

    def test_home_and_away_must_differ(self):
        response = self.client.post(
            self.url, self.payload(away_team=str(self.home.pk))
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertFalse(Match.objects.filter(round_number=2).exists())

    def test_team_from_another_championship_is_rejected(self):
        response = self.client.post(
            self.url, self.payload(away_team=str(self.foreign_team.pk))
        )
        self.assertIn("away_team", response.context["form"].errors)

    def test_date_must_be_within_the_championship(self):
        response = self.client.post(
            self.url, self.payload(scheduled_at="2027-01-10T16:00")
        )
        self.assertIn("scheduled_at", response.context["form"].errors)

    def test_list_groups_by_round_and_filters(self):
        Match.objects.create(
            championship=self.championship,
            home_team=self.away,
            away_team=self.home,
            round_number=2,
            scheduled_at=aware(2026, 10, 27, 16, 0),
        )
        response = self.client.get(reverse("matches:panel"), {"round": "2"})
        self.assertEqual(len(response.context["matches"]), 1)
        self.assertContains(response, "Rodada 2")


class LineupTests(MatchPagesTestCase):
    def setUp(self):
        self.login(self.official)
        self.url = reverse("matches:lineup", args=[self.match.pk, "home"])

    def errors_for(self, data):
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        return response.context["formset"]

    def test_save_valid_lineup(self):
        response = self.client.post(self.url, self.lineup_post_data(self.home))
        self.assertRedirects(
            response, reverse("matches:sheet", args=[self.match.pk])
        )
        lineup = self.match.lineups.filter(team=self.home)
        self.assertEqual(lineup.count(), 14)
        self.assertEqual(lineup.filter(role=Lineup.Role.STARTER).count(), 11)
        self.assertEqual(lineup.filter(is_captain=True).count(), 1)

    def test_too_many_or_too_few_starters(self):
        for starters in (12, services.MIN_STARTERS - 1):
            formset = self.errors_for(
                self.lineup_post_data(self.home, starters=starters, subs=0)
            )
            self.assertTrue(formset.non_form_errors())
        self.assertFalse(self.match.lineups.exists())

    def test_only_one_captain(self):
        data = self.lineup_post_data(self.home)
        data["form-2-is_captain"] = "on"
        self.assertTrue(self.errors_for(data).non_form_errors())

    def test_duplicate_shirt_numbers(self):
        data = self.lineup_post_data(self.home)
        data["form-1-shirt_number"] = data["form-0-shirt_number"]
        self.assertTrue(self.errors_for(data).non_form_errors())

    def test_suspended_player_is_not_offered(self):
        registration = services.lineup_candidates(self.match, self.home)[0]
        PlayerRegistration.objects.filter(pk=registration.pk).update(
            status=PlayerRegistration.Status.SUSPENDED
        )
        candidates = services.lineup_candidates(self.match, self.home)
        self.assertNotIn(registration, candidates)

    def test_listed_player_suspended_later_must_be_removed(self):
        self.set_lineups()
        listed = self.lineup_of(self.home, 3).player_registration
        PlayerRegistration.objects.filter(pk=listed.pk).update(
            status=PlayerRegistration.Status.SUSPENDED
        )
        # Still shown (so it can be removed), but cannot stay listed.
        data = self.lineup_post_data(self.home)
        formset = self.errors_for(data)
        self.assertTrue(any("role" in form.errors for form in formset.forms))

    def test_player_with_events_cannot_be_removed(self):
        self.set_lineups()
        self.login(self.official)
        scorer = self.lineup_of(self.home, 9)
        self.post_event("goal", team=self.home, scorer=scorer)

        data = self.lineup_post_data(self.home)
        index = next(
            i
            for i in range(PLAYERS_PER_TEAM)
            if data[f"form-{i}-registration_id"]
            == str(scorer.player_registration_id)
        )
        data[f"form-{index}-role"] = ""
        data.pop(f"form-{index}-is_captain", None)
        self.assertTrue(self.errors_for(data).non_form_errors())

    def test_closed_match_cannot_be_changed(self):
        Match.objects.filter(pk=self.match.pk).update(
            status=Match.Status.FINISHED
        )
        self.client.post(self.url, self.lineup_post_data(self.home))
        self.assertFalse(self.match.lineups.exists())


class MatchEventTests(MatchPagesTestCase):
    def setUp(self):
        self.set_lineups()
        self.login(self.official)

    def refresh(self):
        self.match.refresh_from_db()
        return self.match.home_score, self.match.away_score

    def test_goal_updates_the_score(self):
        response = self.post_event(
            "goal",
            team=self.home,
            scorer=self.lineup_of(self.home, 9),
            assist=self.lineup_of(self.home, 10),
        )
        self.assertRedirects(
            response, reverse("matches:sheet", args=[self.match.pk])
        )
        self.assertEqual(self.refresh(), (1, 0))
        event = MatchEvent.objects.get()
        self.assertEqual(event.recorded_by, self.official)
        self.assertEqual(event.participants.count(), 2)

    def test_assist_is_optional(self):
        self.post_event(
            "goal", team=self.away, scorer=self.lineup_of(self.away, 9)
        )
        self.assertEqual(self.refresh(), (0, 1))

    def test_own_goal_counts_for_the_opponent(self):
        self.post_event(
            "own-goal",
            team=self.away,
            own_goal_author=self.lineup_of(self.away, 4),
        )
        self.assertEqual(self.refresh(), (1, 0))

    def test_scorer_must_belong_to_the_event_team(self):
        response = self.post_event(
            "goal", team=self.home, scorer=self.lineup_of(self.away, 9)
        )
        self.assertIn("role_scorer", response.context["event_form"].errors)
        self.assertFalse(MatchEvent.objects.exists())

    def test_substitution_needs_two_different_players(self):
        player = self.lineup_of(self.home, 5)
        response = self.post_event(
            "substitution", team=self.home, player_in=player, player_out=player
        )
        self.assertTrue(response.context["event_form"].errors)
        self.assertFalse(MatchEvent.objects.exists())

    def test_cancel_event_restores_the_score(self):
        self.post_event(
            "goal", team=self.home, scorer=self.lineup_of(self.home, 9)
        )
        event = MatchEvent.objects.get()
        cancel_url = reverse(
            "matches:event_cancel", args=[self.match.pk, event.pk]
        )
        self.client.post(cancel_url, {"reason": "Impedimento"})

        event.refresh_from_db()
        self.assertTrue(event.is_canceled)
        self.assertEqual(event.canceled_by, self.official)
        self.assertEqual(event.cancel_reason, "Impedimento")
        self.assertEqual(self.refresh(), (0, 0))

        # A second cancellation is refused.
        self.client.post(cancel_url, {"reason": "De novo"})
        event.refresh_from_db()
        self.assertEqual(event.cancel_reason, "Impedimento")

    def test_shootout_goals_go_to_the_penalty_score(self):
        for team, number in ((self.home, 9), (self.home, 10), (self.away, 9)):
            self.post_event(
                "shootout-goal",
                team=team,
                penalty_taker=self.lineup_of(team, number),
            )
        self.match.refresh_from_db()
        self.assertEqual(
            (self.match.home_penalty_score, self.match.away_penalty_score),
            (2, 1),
        )
        self.assertEqual(self.refresh(), (0, 0))

    def test_event_form_shows_only_roles_of_the_type(self):
        url = reverse("matches:sheet", args=[self.match.pk])
        response = self.client.get(url, {"event_type": "substitution"})
        form = response.context["event_form"]
        self.assertIn("role_player-in", form.fields)
        self.assertNotIn("role_scorer", form.fields)

    def test_closed_match_rejects_new_events(self):
        Match.objects.filter(pk=self.match.pk).update(
            status=Match.Status.FINISHED
        )
        self.post_event(
            "goal", team=self.home, scorer=self.lineup_of(self.home, 9)
        )
        self.assertFalse(MatchEvent.objects.exists())

    def test_event_types_are_seeded(self):
        self.assertTrue(EventType.objects.filter(code="goal").exists())
