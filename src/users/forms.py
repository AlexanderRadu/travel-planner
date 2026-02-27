from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import UserProfile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('Email'))
    first_name = forms.CharField(required=False, label=_('Имя'))
    last_name = forms.CharField(required=False, label=_('Фамилия'))

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'password1',
            'password2',
        ]
        labels = {
            'username': _('Имя пользователя'),
            'password1': _('Пароль'),
            'password2': _('Подтверждение пароля'),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True, label=_('Email'))
    first_name = forms.CharField(required=False, label=_('Имя'))
    last_name = forms.CharField(required=False, label=_('Фамилия'))
    remove_avatar = forms.BooleanField(
        required=False, label=_('Удалить аватар')
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and getattr(self.instance, 'user', None):
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        user = getattr(self.instance, 'user', None)
        if user is not None:
            user.email = self.cleaned_data.get('email')
            user.first_name = self.cleaned_data.get('first_name', '')
            user.last_name = self.cleaned_data.get('last_name', '')
            user.save()

        if self.cleaned_data.get('remove_avatar') and self.instance.avatar:
            self.instance.avatar.delete(save=False)
            self.instance.avatar = None

        return super().save(commit=commit)

    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'location', 'website']
        labels = {
            'bio': _('О себе'),
            'avatar': _('Аватар'),
            'location': _('Местоположение'),
            'website': _('Веб-сайт'),
        }
        widgets = {'bio': forms.Textarea(attrs={'rows': 4})}
