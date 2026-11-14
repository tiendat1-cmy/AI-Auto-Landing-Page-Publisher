import re
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

SOCIAL_DOMAINS = {
    "facebook_url": ("facebook.com", "fb.com"),
    "tiktok_url": ("tiktok.com",),
    "instagram_url": ("instagram.com",),
}


class ProjectCreate(BaseModel):
    template_id: int
    campaign_name: str = Field(min_length=1, max_length=255)
    product_name: str = Field(min_length=1, max_length=255)
    product_description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[Decimal] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_theme: Optional[str] = None
    facebook_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("campaign_name", "product_name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Khong duoc de trong")
        return v

    @field_validator("color_theme")
    @classmethod
    def valid_color(cls, v):
        if v is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("Tong mau phai dang hex, vi du #1A2B3C")
        return v

    @field_validator("image_url", "facebook_url", "tiktok_url", "instagram_url")
    @classmethod
    def valid_url(cls, v, info):
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Link phai bat dau bang http:// hoac https://")
        domains = SOCIAL_DOMAINS.get(info.field_name)
        if domains and not any(
            parsed.hostname == d or parsed.hostname.endswith("." + d) for d in domains
        ):
            raise ValueError("Link khong dung ten mien " + domains[0])
        return v