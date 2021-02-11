from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import AbstractUser

# Create your models here.

# Custom User Class Interiting from the main AbstractUser Class
# We can modify the User class in future if needed
class User(AbstractUser):
    pass


class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username

    class Meta:
        db_table = ""
        managed = True
        verbose_name = "UserProfile"
        verbose_name_plural = "UserProfiles"


class Agent(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    def __str__(self):
        return self.user.username

    class Meta:
        db_table = ""
        managed = True
        verbose_name = "Agent"
        verbose_name_plural = "Agents"


class Lead(models.Model):

    first_name = models.CharField(max_length=20)
    last_name = models.CharField(max_length=20)
    age = models.IntegerField(default=0)
    agent = models.ForeignKey(
        Agent, on_delete=models.CASCADE
    )  # Relationship with Agent table describing that every Lead has one agent

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = ""
        managed = True
        verbose_name = "Lead"
        verbose_name_plural = "Leads"


def post_user_created_signal(sender, instance, created, **kwargs):
    print(instance, created)
    if created:
        UserProfile.objects.create(user=instance)


post_save.connect(post_user_created_signal, sender=User)

