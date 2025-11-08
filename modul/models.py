
# 2024-11-06

import random
from datetime import datetime
from django.utils.timezone import now
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from pytz import utc
import logging

logger = logging.getLogger(__name__)


# ======================================
# USER MANAGER
# ======================================

class CustomUserManager(BaseUserManager):
    """Custom User Manager"""

    def create_user(self, uid, username=None, first_name=None, last_name=None,
                    profile_image=None, password=None, **extra_fields):
        """Oddiy foydalanuvchi yaratish"""
        if not uid:
            raise ValueError('Foydalanuvchi UID ga ega bo\'lishi kerak')

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
        return user

    def create_superuser(self, uid, username=None, first_name=None, last_name=None,
                         profile_image=None, password=None, **extra_fields):
        """Superuser yaratish"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser is_staff=True bo\'lishi kerak')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser is_superuser=True bo\'lishi kerak')

        return self.create_user(uid, username, first_name, last_name,
                                profile_image, password, **extra_fields)


# ======================================
# ENUMS
# ======================================

class SexEnum(models.TextChoices):
    MALE = "MALE", "Male"
    FEMALE = "FEMALE", "Female"
    ANY = "ANY", "Any"


class MediaTypeEnum(models.TextChoices):
    PHOTO = "PHOTO", "Photo"
    VIDEO = "VIDEO", "Video"
    VIDEO_NOTE = "VIDEO_NOTE", "Video Note"


class GPTTypeEnum(models.TextChoices):
    REQUEST = "REQUEST", "Request"
    PICTURE = "PICTURE", "Picture"
    TEXT_TO_SPEECH = "TEXT_TO_SPEECH", "Text to Speech"
    SPEECH_TO_TEXT = "SPEECH_TO_TEXT", "Speech to Text"
    ASSISTANT = "ASSISTANT", "Assistant"


class TaskTypeEnum(models.TextChoices):
    DOWNLOAD_MEDIA = "DOWNLOAD_MEDIA", "Download Media"


class BroadcastTypeEnum(models.TextChoices):
    TEXT = "TEXT", "Text"
    PHOTO = "PHOTO", "Photo"
    VIDEO = "VIDEO", "Video"
    VIDEO_NOTE = "VIDEO_NOTE", "Video Note"
    AUDIO = "AUDIO", "Audio"


# ======================================
# ASOSIY MODELLAR
# ======================================

class ReferralCode(models.Model):
    """Referral kodlar"""
    code = models.CharField(max_length=255, unique=True, db_index=True)  # ✅
    user = models.ForeignKey('User', related_name="referral_codes", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return self.code

    class Meta:
        db_table = "referral_codes"
        indexes = [
            models.Index(fields=['code']),  # ✅
            models.Index(fields=['created_at']),  # ✅
        ]


class User(AbstractBaseUser, PermissionsMixin):
    """
    Asosiy foydalanuvchi modeli
    ✅ YANGILANDI: db_index va indexes qo'shildi
    """
    uid = models.BigIntegerField(unique=True, null=True, db_index=True)  # ✅
    username = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)  # ✅
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    profile_image = models.FileField(upload_to='images', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅
    is_active = models.BooleanField(default=True, db_index=True)  # ✅
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
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['username']),
            models.Index(fields=['uid', 'is_active']),
            models.Index(fields=['created_at']),
        ]


class Bot(models.Model):
    """
    Bot modeli
    ✅ YANGILANDI: db_index va indexes qo'shildi
    """
    token = models.CharField(max_length=255, unique=True, db_index=True)  # ✅
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bots", db_index=True)  # ✅
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name="child_bots")
    bot_enable = models.BooleanField(default=True, db_index=True)  # ✅
    username = models.CharField(max_length=255, db_index=True)  # ✅
    unauthorized = models.BooleanField(default=False)
    photo = models.CharField(max_length=255, null=True, blank=True)
    photo_is_gif = models.BooleanField(default=False)
    news_channel = models.CharField(max_length=255, null=True, blank=True)
    support = models.CharField(max_length=32, null=True, blank=True)
    mandatory_subscription = models.BooleanField(default=False)
    enable_promotion = models.BooleanField(default=False)
    enable_child_bot = models.BooleanField(default=False)
    enable_download = models.BooleanField(default=False)
    enable_leo = models.BooleanField(default=False)
    enable_chatgpt = models.BooleanField(default=False)
    enable_anon = models.BooleanField(default=False)
    enable_refs = models.BooleanField(default=False)
    enable_kino = models.BooleanField(default=False)
    enable_davinci = models.BooleanField(default=False)

    def __str__(self):
        enabled_modules = []
        module_names = {
            'enable_davinci': 'Davinci',
            'enable_download': 'Загрузка',
            'enable_leo': 'Лео',
            'enable_chatgpt': 'ChatGPT',
            'enable_anon': 'Анонимный чат',
            'enable_refs': 'Рефералы',
            'enable_kino': 'Кино'
        }

        for field, name in module_names.items():
            if getattr(self, field):
                enabled_modules.append(name)

        if enabled_modules:
            return f"{', '.join(enabled_modules)}"
        else:
            return f"{self.username} (Нет активных модулей)"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['username']),
            models.Index(fields=['owner', 'bot_enable']),
            models.Index(fields=['bot_enable']),
        ]


class UserTG(models.Model):
    """
    Telegram foydalanuvchisi
    ✅ YANGILANDI: db_index va indexes qo'shildi
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tg_profile',
        null=True,
        blank=True
    )
    uid = models.BigIntegerField(unique=True, db_index=True)  # ✅
    username = models.CharField(max_length=255, null=True, blank=True, db_index=True)  # ✅
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    balance = models.FloatField(default=0)
    paid = models.FloatField(default=0)
    refs = models.IntegerField(default=0)
    invited = models.CharField(max_length=255, default="Никто")
    invited_id = models.BigIntegerField(null=True, default=None, db_index=True)  # ✅
    banned = models.BooleanField(default=False, db_index=True)  # ✅
    last_interaction = models.DateTimeField(null=True, blank=True, default=datetime.now(tz=utc), db_index=True)  # ✅
    interaction_count = models.IntegerField(null=True, blank=True, default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅
    user_link = models.CharField(unique=True, null=True, max_length=2056)
    greeting = models.CharField(default="Добро пожаловать!", max_length=255, null=True)

    def __str__(self):
        return self.username or f'User {self.uid}'

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['uid']),
            models.Index(fields=['username']),
            models.Index(fields=['banned', 'uid']),
            models.Index(fields=['created_at']),
            models.Index(fields=['invited_id']),
            models.Index(fields=['last_interaction']),
        ]


class ClientBotUser(models.Model):
    """
    Bot foydalanuvchisi
    ✅ YANGILANDI: db_index va indexes qo'shildi
    """
    user = models.ForeignKey(UserTG, on_delete=models.CASCADE, related_name="client_bot_users", db_index=True)  # ✅
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="clients", db_index=True)  # ✅
    uid = models.BigIntegerField(db_index=True)  # ✅
    balance = models.FloatField(default=0)
    referral_count = models.IntegerField(default=0)
    referral_balance = models.FloatField(default=0)
    inviter = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='referrals')
    inviter_got_bonus = models.BooleanField(default=False)
    subscribed_all_chats = models.BooleanField(default=False)
    subscribed_chats_at = models.DateTimeField(default=datetime(1970, 1, 1, tzinfo=utc))
    current_ai_limit = models.IntegerField(default=12)
    enable_horoscope_everyday_alert = models.BooleanField(default=False)

    def __str__(self):
        return f'ClientBotUser {self.uid}'

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['uid', 'bot']),
            models.Index(fields=['bot', 'uid']),
            models.Index(fields=['user']),
            models.Index(fields=['bot']),
        ]


class SystemChannel(models.Model):
    """
    Tizim kanallari
    ✅ YANGILANDI: db_index qo'shildi
    """
    channel_id = models.BigIntegerField(unique=True, db_index=True)  # ✅
    channel_url = models.CharField(max_length=255)
    title = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)  # ✅
    added_by_user_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return self.title or f'Channel {self.channel_id}'

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['channel_id']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]


# ======================================
# LEO MATCH MODELLARI
# ======================================

class LeoMatchModel(models.Model):
    """
    Leo tanishish moduli
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)  # ✅
    photo = models.CharField(max_length=1024)
    media_type = models.CharField(max_length=50, choices=MediaTypeEnum.choices)
    sex = models.CharField(max_length=50, choices=SexEnum.choices)
    age = models.IntegerField()
    full_name = models.CharField(max_length=15)
    about_me = models.CharField(max_length=300)
    city = models.CharField(max_length=50)
    which_search = models.CharField(max_length=50, choices=SexEnum.choices)
    search = models.BooleanField(default=True, db_index=True)  # ✅
    active = models.BooleanField(default=True, db_index=True)  # ✅
    bot_username = models.CharField(max_length=100, db_index=True)  # ✅
    count_likes = models.IntegerField(default=0)
    blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅
    updated_at = models.DateTimeField(auto_now=True)
    admin_checked = models.BooleanField(default=False)
    couple_notifications_stopped = models.BooleanField(default=False)
    rate_list = models.TextField(default='|', blank=True)
    gallery = models.TextField(default='[]', blank=True)

    def __str__(self):
        return self.full_name

    class Meta:
        unique_together = ['user', 'bot_username']
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user', 'bot_username']),
            models.Index(fields=['bot_username', 'active', 'search']),
            models.Index(fields=['sex', 'city']),
            models.Index(fields=['created_at']),
        ]


class LeoMatchLikesBasketModel(models.Model):
    """
    Leo like lar va match lar
    ✅ YANGILANDI: db_index qo'shildi
    """
    from_user = models.ForeignKey(LeoMatchModel, related_name="leo_match_from_user", on_delete=models.CASCADE,
                                  db_index=True)  # ✅
    to_user = models.ForeignKey(LeoMatchModel, related_name="leo_match_to_user", on_delete=models.CASCADE,
                                db_index=True)  # ✅
    message = models.CharField(max_length=1024, null=True, blank=True)
    done = models.BooleanField(default=False, db_index=True)  # ✅
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅
    like_type = models.CharField(max_length=10, default='like')
    media_file_id = models.CharField(max_length=255, null=True, blank=True)
    media_type = models.CharField(max_length=20, null=True, blank=True)
    is_mutual = models.BooleanField(default=False, db_index=True)  # ✅
    viewed = models.BooleanField(default=False)

    def __str__(self):
        return f"From {self.from_user} to {self.to_user}"

    class Meta:
        unique_together = ['from_user', 'to_user']
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['from_user', 'to_user']),
            models.Index(fields=['to_user', 'done']),
            models.Index(fields=['is_mutual']),
            models.Index(fields=['created_at']),
        ]


# ======================================
# GPT VA TASK MODELLARI
# ======================================

class GPTRecordModel(models.Model):
    """
    GPT so'rovlar tarixi
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(UserTG, on_delete=models.CASCADE, db_index=True)  # ✅
    bot = models.ForeignKey(User, related_name="bot_user", on_delete=models.CASCADE, db_index=True)  # ✅
    message = models.CharField(max_length=1024)
    type = models.CharField(max_length=50, choices=GPTTypeEnum.choices, db_index=True)  # ✅
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return f"{self.type} - {self.message}"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user', 'bot']),
            models.Index(fields=['type']),
            models.Index(fields=['created_at']),
        ]


class DavinciStopWords(models.Model):
    """
    Davinci taqiqlangan so'zlar
    ✅ YANGILANDI: db_index qo'shildi
    """
    word = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅
    is_active = models.BooleanField(default=True, db_index=True)  # ✅

    def __str__(self):
        return f"Stop Word: {self.word}"

    class Meta:
        db_table = 'davinci_stopwords'
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
        ]


class TaskModel(models.Model):
    """
    Vazifalar
    ✅ YANGILANDI: db_index qo'shildi
    """
    client = models.ForeignKey(ClientBotUser, on_delete=models.CASCADE, db_index=True)  # ✅
    task_type = models.CharField(max_length=50, choices=TaskTypeEnum.choices, db_index=True)  # ✅
    data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return f"{self.task_type} for {self.client}"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['client']),
            models.Index(fields=['task_type']),
            models.Index(fields=['created_at']),
        ]


# ======================================
# ANON CHAT MODELLARI
# ======================================

class AnonClientModel(models.Model):
    """
    Anonim chat mijoz
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(UserTG, on_delete=models.CASCADE, db_index=True)  # ✅
    sex = models.CharField(max_length=50, choices=SexEnum.choices, default='ANY')
    which_search = models.CharField(max_length=50, choices=SexEnum.choices, default='ANY')
    status = models.IntegerField(default=0, db_index=True)  # ✅
    vip_date_end = models.DateTimeField(null=True)
    job_id = models.CharField(max_length=255, null=True)
    bot_username = models.CharField(max_length=100, default="", db_index=True)  # ✅

    def __str__(self):
        return f"Anon Client {self.user.uid} - {self.bot_username}"

    class Meta:
        unique_together = ['user', 'bot_username']
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user', 'bot_username']),
            models.Index(fields=['bot_username', 'status']),
            models.Index(fields=['status']),
        ]


class AnonChatModel(models.Model):
    """
    Anonim chat
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(AnonClientModel, related_name="anon_chat_user", on_delete=models.CASCADE,
                             db_index=True)  # ✅
    partner = models.ForeignKey(AnonClientModel, related_name="anon_chat_partner", on_delete=models.CASCADE,
                                db_index=True)  # ✅
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return f"Chat between {self.user} and {self.partner}"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['partner']),
            models.Index(fields=['created_at']),
        ]


# ======================================
# SMS VA TO'LOV MODELLARI
# ======================================

class SMSBanModel(models.Model):
    """
    SMS ban
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(UserTG, on_delete=models.CASCADE, db_index=True)  # ✅
    service = models.CharField(max_length=100, db_index=True)  # ✅
    phone = models.CharField(max_length=50)

    def __str__(self):
        return f"SMS Ban {self.service} for {self.user}"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['service']),
        ]


class SMSOrder(models.Model):
    """
    SMS buyurtma
    ✅ YANGILANDI: db_index qo'shildi
    """
    user = models.ForeignKey(UserTG, on_delete=models.CASCADE, db_index=True)  # ✅
    order_id = models.BigIntegerField(unique=True, db_index=True)  # ✅
    country_code = models.CharField(max_length=20, default="")
    product = models.CharField(max_length=255)
    phone = models.CharField(max_length=255)
    receive_code = models.CharField(max_length=255, default="")
    receive_status = models.CharField(max_length=10, default="wait", db_index=True)  # ✅
    price = models.FloatField()
    order_created_at = models.DateTimeField(auto_now=True, db_index=True)  # ✅
    profit = models.FloatField(default=0)
    bot_admin_profit = models.FloatField(default=0)
    msg_id = models.BigIntegerField(null=True)

    def __str__(self):
        return f"SMS Order {self.order_id} for {self.user}"

    class Meta:
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['order_id']),
            models.Index(fields=['receive_status']),
            models.Index(fields=['order_created_at']),
        ]


class PaymentTransaction(models.Model):
    """
    To'lov tranzaksiyalari
    ✅ YANGILANDI: db_index qo'shildi
    """
    user_id = models.BigIntegerField(db_index=True)  # ✅
    bot_id = models.BigIntegerField(db_index=True)  # ✅
    amount_rubles = models.FloatField()
    amount_stars = models.IntegerField()
    payment_id = models.CharField(max_length=255, db_index=True)  # ✅
    status = models.CharField(max_length=50, default='completed', db_index=True)  # ✅
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    def __str__(self):
        return f"Payment {self.payment_id} - {self.status}"

    class Meta:
        db_table = 'payment_transactions'
        # ✅ YANGI - indexes qo'shildi
        indexes = [
            models.Index(fields=['user_id', 'bot_id']),
            models.Index(fields=['payment_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['created_at']),
        ]


# ======================================
# YORDAMCHI MODELLAR
# ======================================

class Checker(models.Model):
    """Tekshiruvchi"""
    tg_id = models.IntegerField(unique=True, db_index=True)  # ✅
    inv_id = models.IntegerField()
    add = models.BooleanField(default=False)

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['tg_id']),
        ]


class Withdrawals(models.Model):
    """Pul yechish"""
    tg_id = models.ForeignKey('UserTG', on_delete=models.CASCADE, to_field='uid')
    amount = models.FloatField()
    card = models.CharField(max_length=255)
    bank = models.CharField(max_length=255)
    status = models.CharField(max_length=255, default="ожидание", db_index=True)  # ✅
    reg_date = models.DateTimeField(db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['reg_date']),
        ]


class Channels(models.Model):
    """Kanallar"""
    channel_url = models.CharField(max_length=255, unique=True)
    channel_id = models.BigIntegerField(unique=True, db_index=True)  # ✅
    admins_channel = models.BooleanField(default=False)

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['channel_id']),
        ]


class AdminInfo(models.Model):
    """Admin ma'lumotlari"""
    admin_channel = models.CharField(max_length=255)
    price = models.FloatField(default=3.0)
    min_amount = models.FloatField(default=30.0)
    bot_token = models.CharField(max_length=255, null=True, blank=True, unique=True, db_index=True)  # ✅

    class Meta:
        db_table = 'admin_info'
        # ✅ YANGI
        indexes = [
            models.Index(fields=['bot_token']),
        ]


class ChannelSponsor(models.Model):
    """Kanal homiy"""
    chanel_id = models.BigIntegerField(db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['chanel_id']),
        ]


class Messages(models.Model):
    """Xabarlar"""
    sender_id = models.BigIntegerField(db_index=True)  # ✅
    receiver_id = models.BigIntegerField(db_index=True)  # ✅
    sender_message_id = models.BigIntegerField()
    receiver_message_id = models.BigIntegerField()
    reg_date = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['sender_id', 'receiver_id']),
            models.Index(fields=['reg_date']),
        ]


class DownloadAnalyticsModel(models.Model):
    """Download statistikasi"""
    bot_username = models.CharField(max_length=100, db_index=True)  # ✅
    domain = models.CharField(max_length=1024)
    count = models.IntegerField(default=0)
    date = models.DateTimeField(default=timezone.now, db_index=True)  # ✅

    def __str__(self):
        return f"{self.bot_username} - {self.domain} - {self.count}"

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['bot_username', 'date']),
            models.Index(fields=['date']),
        ]


class Link_statistic(models.Model):
    """Link statistikasi"""
    user_id = models.BigIntegerField(db_index=True)  # ✅
    reg_date = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['reg_date']),
        ]


class Answer_statistic(models.Model):
    """Javob statistikasi"""
    user_id = models.IntegerField(db_index=True)  # ✅
    reg_date = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['reg_date']),
        ]


class Rating_today(models.Model):
    """Bugungi reyting"""
    user_id = models.IntegerField(db_index=True)  # ✅
    amount = models.IntegerField()
    reg_date = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['user_id', 'reg_date']),
            models.Index(fields=['reg_date']),
        ]


class Rating_overall(models.Model):
    """Umumiy reyting"""
    user_id = models.IntegerField(db_index=True)  # ✅
    amount = models.IntegerField()
    reg_date = models.DateTimeField(auto_now_add=True, db_index=True)  # ✅

    class Meta:
        # ✅ YANGI
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['amount']),
            models.Index(fields=['reg_date']),
        ]

