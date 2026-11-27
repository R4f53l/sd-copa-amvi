"""Read-only queries about championships shared by several pages."""

from .models import Championship

# Drafts are not published yet; canceled editions are not shown.
HIDDEN_STATUSES = (Championship.Status.DRAFT, Championship.Status.CANCELED)


def public_championships():
    """Editions visitors can see, most recent first."""
    return Championship.objects.exclude(status__in=HIDDEN_STATUSES).order_by(
        "-season", "name"
    )


def featured_championship():
    """The public edition being played; otherwise the most recent one."""
    editions = public_championships()
    return (
        editions.filter(status=Championship.Status.ONGOING).first()
        or editions.order_by("-season", "-start_date").first()
    )
