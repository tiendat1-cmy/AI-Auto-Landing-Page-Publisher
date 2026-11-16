import re
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator
from services.cta_service import (
    clean_string,
    normalize_hotline,
    normalize_instagram,
    normalize_messenger,
    normalize_tiktok_shop,
    normalize_zalo,
)


class ProjectCreate(BaseModel):
    template_id: int
    campaign_name: str = Field(min_length=1, max_length=255)
    product_name: str = Field(min_length=1, max_length=255)
    product_description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[Decimal] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_theme: Optional[str] = None

    # 5 trường CTA động chính thức
    messenger_link: Optional[str] = Field(default=None, max_length=500)
    tiktok_shop_link: Optional[str] = Field(default=None, max_length=500)
    zalo_link: Optional[str] = Field(default=None, max_length=500)
    instagram_link: Optional[str] = Field(default=None, max_length=500)
    hotline: Optional[str] = Field(default=None, max_length=50)

    # Các trường cũ giữ lại để tương thích ngược
    facebook_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("campaign_name", "product_name")
    @classmethod
    def not_blank(cls, v):
        v = v.strip() if v else ""
        if not v:
            raise ValueError("Không được để trống")
        return v

    @field_validator("color_theme")
    @classmethod
    def valid_color(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError("Tông màu phải có dạng mã hex, ví dụ #1A2B3C")
        return v

    @field_validator("image_url")
    @classmethod
    def valid_image_url(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Đường dẫn ảnh phải bắt đầu bằng http:// hoặc https://")
        return v

    @field_validator("messenger_link")
    @classmethod
    def validate_messenger(cls, v):
        return clean_string(v)

    @field_validator("tiktok_shop_link")
    @classmethod
    def validate_tiktok_shop(cls, v):
        return clean_string(v)

    @field_validator("zalo_link")
    @classmethod
    def validate_zalo(cls, v):
        return clean_string(v)

    @field_validator("instagram_link")
    @classmethod
    def validate_instagram(cls, v):
        return clean_string(v)

    @field_validator("hotline")
    @classmethod
    def validate_hotline(cls, v):
        return clean_string(v)


class ProjectUpdate(BaseModel):
    template_id: Optional[int] = None
    campaign_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product_description: Optional[str] = Field(default=None, max_length=5000)
    price: Optional[Decimal] = Field(default=None, ge=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    color_theme: Optional[str] = None

    # 5 trường CTA động chính thức
    messenger_link: Optional[str] = Field(default=None, max_length=500)
    tiktok_shop_link: Optional[str] = Field(default=None, max_length=500)
    zalo_link: Optional[str] = Field(default=None, max_length=500)
    instagram_link: Optional[str] = Field(default=None, max_length=500)
    hotline: Optional[str] = Field(default=None, max_length=50)

    # Các trường cũ
    facebook_url: Optional[str] = Field(default=None, max_length=500)
    tiktok_url: Optional[str] = Field(default=None, max_length=500)
    instagram_url: Optional[str] = Field(default=None, max_length=500)
    raw_json_data: Optional[Any] = None

    @field_validator("campaign_name", "product_name")
    @classmethod
    def not_blank(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Không được để trống")
        return v

    @field_validator("color_theme")
    @classmethod
    def valid_color(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
                raise ValueError("Tông màu phải có dạng mã hex, ví dụ #1A2B3C")
        return v

    @field_validator("image_url")
    @classmethod
    def valid_image_url(cls, v):
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Đường dẫn ảnh phải bắt đầu bằng http:// hoặc https://")
        return v

    @field_validator("messenger_link")
    @classmethod
    def validate_messenger(cls, v):
        return clean_string(v)

    @field_validator("tiktok_shop_link")
    @classmethod
    def validate_tiktok_shop(cls, v):
        return clean_string(v)

    @field_validator("zalo_link")
    @classmethod
    def validate_zalo(cls, v):
        return clean_string(v)

    @field_validator("instagram_link")
    @classmethod
    def validate_instagram(cls, v):
        return clean_string(v)

    @field_validator("hotline")
    @classmethod
    def validate_hotline(cls, v):
        return clean_string(v)
