from django import forms

class UpdateForm(forms.Form):
    actions = (
        ('items', 'Get items'),
        ('recipes', 'Get recipes'),
    )
    action = forms.ChoiceField(actions, required=True)
