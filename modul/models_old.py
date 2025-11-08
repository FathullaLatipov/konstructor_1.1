# models.py - YAXSHILANGAN VERSIYA
# Faqat asosiy model larni ko'rsataman

import random
from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.utils import timezone
from django.core.validators import MinLengthValidator
import logging

logger = logging.getLogger(__name__)


class CustomUserManager(BaseUserManager):
    """Custom User Manager"""

    def create_user(self, uid, username=None, first_name=None,
                    last_name=None, profile_image=None, password=None, **extra_fields):
        """Oddiy foydalanuvchi yaratish"""
        if not uid:
            raise ValueError('Foydalanuvchi UID ga ega bo\'lishikerak')

            user = self.model(
                uid=uid,
                username=username,
                first_name=first_name,
                last_name=last_name,
                profile_image=profile_image,
                **extra_fields
            )

            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()

            user.save(using=self._db)
            logger.info(f"User created: {uid}")
        return user

    def create_superuser(self, uid, username=None, first_name=None,
                         last_name=None, profile_image=None, password=None, **extra_fields):
        """Superuser yaratish"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser is_staff=True bo\'lishi kerak')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser is_superuser=True bo\'lishi kerak')

        return self.create_user(uid, username, first_name, last_name,
                                profile_image, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Asosiy foydalanuvchi modeli"""

    uid = models.BigIntegerField(unique=True, null=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    profile_image = models.FileField(upload_to='images', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'uid'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        """UID avtomatik yaratish"""
        if not self.uid:
            self.uid = random.randint(1000000000, 9999999999)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username or f'User {self.uid}'

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        db_table = 'users'
        indexes = [
            models.Index(fields=['uid', 'is_active']),
            models.Index(fields=['username']),
            models.Index(fields=['created_at']),
        ]


class Bot(models.Model):
    """Bot modeli"""

    token = models.CharField(
        max_length=255,
        unique=True,
        validators=[MinLengthValidator(30)],
        db_index=True
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bots",
        db_index=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_bots"
    )

    bot_enable = models.BooleanField(default=True, db_index=True)
    username = models.CharField(max_length=255, db_index=True)
    unauthorized = models.BooleanField(default=False)

    # Media
    photo = models.CharField(max_length=255, null=True, blank=True)
    photo_is_gif = models.BooleanField(default=False)

    # Sozlamalar
    news_channel = models.CharField(max_length=255, null=True, blank=True)
    support = models.CharField(max_length=32, null=True, blank=True)
    mandatory_subscription = models.BooleanField(default=False)

    # Modullar
    enable_promotion = models.BooleanField(default=False)
    enable_child_bot = models.BooleanField(default=False)
    enable_download = models.BooleanField(default=False, db_index=True)
    enable_leo = models.BooleanField(default=False, db_index=True)
    enable_chatgpt = models.BooleanField(default=False, db_index=True)
    enable_anon = models.BooleanField(default=False)
    enable_refs = models.BooleanField(default=False)
    enable_kino = models.BooleanField(default=False)
    enable_davinci = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({'active' if self.bot_enable else 'inactive'})"

    @property
    def enabled_modules(self):
        """Yoqilgan modullar ro'yxati"""
        modules = []
        module_names = {
            'enable_davinci': 'Davinci',
            'enable_download': 'Download',
            'enable_leo': 'Leo',
            'enable_chatgpt': 'ChatGPT',
            'enable_anon': 'Anonymous',
            'enable_refs': 'Referrals',
            'enable_kino': 'Kino'
        }

        for field, name in module_names.items():
            if getattr(self, field):
                modules.append(name)

        return modules

    class Meta:
        db_table = 'bots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', 'bot_enable']),
            models.Index(fields=['token']),
            models.Index(fields=['username']),
            models.Index(fields=['created_at']),
            models.Index(fields=['enable_leo', 'bot_enable']),
            models.Index(fields=['enable_refs', 'bot_enable']),
        ]


class UserTG(models.Model):
    """Telegram foydalanuvchisi"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='tg_profile',
        null=True,
        blank=True
    )
    uid = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True, blank=True)

    # Balance va statistika
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refs = models.IntegerField(default=0, db_index=True)

    # Referral
    invited = models.CharField(max_length=255, default="Никто")
    invited_id = models.BigIntegerField(null=True, default=None, db_index=True)

    # Status
    banned = models.BooleanField(default=False, db_index=True)

    # Activity tracking
    last_interaction = models.DateTimeField(default=timezone.now, db_index=True)
    interaction_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Qo'shimcha
    user_link = models.CharField(unique=True, null=True, max_length=2056)
    greeting = models.CharField(default="Добро пожаловать!", max_length=255, null=True)

    def __str__(self):
        return self.username or f'User {self.uid}'

    def update_activity(self):
        """Activity ni yangilash"""
        self.last_interaction = timezone.now()
        self.interaction_count += 1
        self.save(update_fields=['last_interaction', 'interaction_count'])

    class Meta:
        db_table = 'users_tg'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['username']),
            models.Index(fields=['banned', 'uid']),
            models.Index(fields=['created_at']),
            models.Index(fields=['last_interaction']),
            models.Index(fields=['invited_id']),
        ]


class ClientBotUser(models.Model):
    """Bot foydalanuvchisi (bot va user orasidagi bog'lanish)"""

    user = models.ForeignKey(
        UserTG,
        on_delete=models.CASCADE,
        related_name="client_bot_users",
        db_index=True
    )
    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE,
        related_name="clients",
        db_index=True
    )
    uid = models.BigIntegerField(db_index=True)

    # Balance
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Referral
    referral_count = models.IntegerField(default=0)
    referral_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    inviter = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )
    inviter_got_bonus = models.BooleanField(default=False)

    # Subscription
    subscribed_all_chats = models.BooleanField(default=False)
    subscribed_chats_at = models.DateTimeField(default=timezone.now)

    # Limits
    current_ai_limit = models.IntegerField(default=12)

    # Settings
    enable_horoscope_everyday_alert = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'User {self.uid} in Bot {self.bot.username}'

    def add_balance(self, amount):
        """Balansga qo'shish"""
        self.balance += amount
        self.save(update_fields=['balance'])

    def subtract_balance(self, amount):
        """Balansdan ayirish"""
        if self.balance >= amount:
            self.balance -= amount
            self.save(update_fields=['balance'])
            return True
        return False

    class Meta:
        db_table = 'client_bot_users'
        unique_together = [['uid', 'bot']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uid', 'bot']),
            models.Index(fields=['bot', 'uid']),
            models.Index(fields=['bot', 'created_at']),
            models.Index(fields=['inviter']),
            models.Index(fields=['user', 'bot']),
        ]


class SystemChannel(models.Model):
    """Sistema kanallari"""

    channel_id = models.BigIntegerField(unique=True, db_index=True)
    channel_url = models.CharField(max_length=255)
    title = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)
    added_by_user_id = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f'Channel {self.channel_id}'

    class Meta:
        db_table = 'system_channels'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel_id']),
            models.Index(fields=['is_active']),
        ]


class PaymentTransaction(models.Model):
    """To'lov tranzaksiyalari"""

    user_id = models.BigIntegerField(db_index=True)
    bot_id = models.BigIntegerField(db_index=True)

    amount_rubles = models.DecimalField(max_digits=10, decimal_places=2)
    amount_stars = models.IntegerField()

    payment_id = models.CharField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=50,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Payment {self.payment_id} - {self.status}'

    class Meta:
        db_table = 'payment_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', 'bot_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['payment_id']),
        ]