from django import forms

class BaseForm(forms.Form):
    """Alla formulär ärver denna för att få Bootstrap-styling automatiskt."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Ge 'form-control' till alla inputs (inte radio/checkbox)
            if not isinstance(field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple)):
                existing_classes = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = f"{existing_classes} form-control".strip()