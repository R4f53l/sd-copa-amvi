"""Form helpers shared by the bounded contexts."""

from django import forms


class BootstrapFormMixin:
    """
    Add Bootstrap 5 CSS classes to every widget of the form.

    Forms that add fields after ``__init__`` must call
    ``apply_bootstrap_classes()`` again once those fields exist.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap_classes()

    def apply_bootstrap_classes(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.HiddenInput):
                continue
            if isinstance(
                widget,
                (
                    forms.CheckboxInput,
                    forms.CheckboxSelectMultiple,
                    forms.RadioSelect,
                ),
            ):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            classes = widget.attrs.get("class", "").split()
            if css_class not in classes:
                classes.append(css_class)
            widget.attrs["class"] = " ".join(classes)
