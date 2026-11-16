"""Dịch vụ xử lý và chuẩn hóa các liên kết CTA (Call-to-Action) động.

Hỗ trợ 5 kênh chính:
1. Messenger (Facebook Messenger)
2. TikTok Shop
3. Zalo
4. Instagram
5. Hotline

Tuân thủ nghiêm ngặt quy tắc:
- Có dữ liệu hợp lệ: Chuẩn hóa URL an toàn với HTTPS hoặc tel:.
- Không có dữ liệu hoặc không hợp lệ: Trả về None (để ẩn hoàn toàn nút).
- Không tạo link rỗng, '#' hoặc liên kết hỏng.
"""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


def clean_string(val: Optional[str]) -> Optional[str]:
    """Loại bỏ khoảng trắng thừa hoặc trả về None nếu rỗng."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def normalize_messenger(val: Optional[str]) -> Optional[str]:
    """Chuẩn hóa đường dẫn Messenger.
    
    Quy tắc:
    - Nhận URL đầy đủ hoặc username/ID.
    - Nếu là username/ID: chuẩn hóa thành https://m.me/{username}.
    - Nếu là URL Messenger hợp lệ: đảm bảo dùng https:// và giữ nguyên.
    - Bỏ tiền tố '@' nếu người dùng nhập.
    """
    raw = clean_string(val)
    if not raw or raw in ("#", "/"):
        return None

    # Bỏ tiền tố @ nếu có
    if raw.startswith("@"):
        raw = raw[1:].strip()
    if not raw:
        return None

    # Nếu là URL đầy đủ (m.me, messenger.com, facebook.com/messages)
    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if any(d in host for d in ("m.me", "messenger.com", "facebook.com", "fb.com")):
            return raw.replace("http://", "https://")
        # Nếu nhập URL khác nhưng có path username, trích xuất phần path
        path = parsed.path.strip("/")
        if path:
            return f"https://m.me/{path}"
        return None

    if "m.me/" in lower:
        return "https://" + raw.lstrip("/")

    # Nếu chỉ là username hoặc ID số (chỉ chứa chữ cái, số, dấu chấm, gạch dưới)
    clean_username = re.sub(r"[^\w\.\-]", "", raw)
    if clean_username:
        return f"https://m.me/{clean_username}"

    return None


def normalize_tiktok_shop(val: Optional[str]) -> Optional[str]:
    """Chuẩn hóa liên kết TikTok Shop.
    
    Quy tắc:
    - Nhận URL cửa hàng TikTok Shop.
    - Đảm bảo sử dụng HTTPS.
    - Không tự ý tạo username hoặc đường dẫn khi dữ liệu không hợp lệ.
    """
    raw = clean_string(val)
    if not raw or raw in ("#", "/"):
        return None

    # Nếu bắt đầu bằng http:// hoặc https://
    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if "tiktok.com" in host or "tiktokshop.com" in host:
            return raw.replace("http://", "https://")
        return None

    # Nếu nhập dạng shop.tiktok.com/... hoặc tiktok.com/@...
    if "tiktok.com" in lower or "tiktokshop.com" in lower:
        return f"https://{raw.lstrip('/')}"

    # Dữ liệu không phải link TikTok Shop hợp lệ -> Không tự ý tạo
    return None


def normalize_zalo(val: Optional[str]) -> Optional[str]:
    """Chuẩn hóa liên kết Zalo.
    
    Quy tắc:
    - Nếu nhập số điện thoại: chuẩn hóa thành https://zalo.me/{phone}.
    - Nếu nhập link Zalo hợp lệ: giữ nguyên và đảm bảo HTTPS.
    """
    raw = clean_string(val)
    if not raw or raw in ("#", "/"):
        return None

    # Bỏ tiền tố @ nếu có
    if raw.startswith("@"):
        raw = raw[1:].strip()

    lower = raw.lower()
    if "zalo.me" in lower:
        if lower.startswith("http://") or lower.startswith("https://"):
            return raw.replace("http://", "https://")
        return f"https://{raw.lstrip('/')}"

    # Kiểm tra xem có phải định dạng số điện thoại (chứa số, dấu cách, dấu chấm, dấu cộng)
    # Ví dụ: 0987 654 321, +84987654321, 0987.654.321
    clean_phone = re.sub(r"[\s\.\-\(\)]", "", raw)
    if re.fullmatch(r"(\+84|84|0)[0-9]{8,11}", clean_phone):
        # Chuyển +84 hoặc 84 về đầu 0 nếu cần, hoặc để nguyên format zalo.me
        if clean_phone.startswith("+"):
            clean_phone = clean_phone[1:]
        return f"https://zalo.me/{clean_phone}"

    # Nếu là chuỗi số thuần từ 9-11 chữ số
    if clean_phone.isdigit() and 8 <= len(clean_phone) <= 12:
        return f"https://zalo.me/{clean_phone}"

    return None


def normalize_instagram(val: Optional[str]) -> Optional[str]:
    """Chuẩn hóa liên kết Instagram.
    
    Quy tắc:
    - Nhận URL đầy đủ hoặc username.
    - Nếu là username: chuẩn hóa thành https://www.instagram.com/{username}/.
    - Bỏ tiền tố '@' nếu có.
    """
    raw = clean_string(val)
    if not raw or raw in ("#", "/"):
        return None

    if raw.startswith("@"):
        raw = raw[1:].strip()
    if not raw:
        return None

    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower()
        if "instagram.com" in host or "instagr.am" in host:
            clean_url = raw.replace("http://", "https://")
            if not clean_url.endswith("/"):
                clean_url += "/"
            return clean_url
        path = parsed.path.strip("/")
        if path:
            return f"https://www.instagram.com/{path}/"
        return None

    if "instagram.com/" in lower:
        clean_url = "https://" + raw.lstrip("/")
        if not clean_url.endswith("/"):
            clean_url += "/"
        return clean_url

    # Nếu là username hợp lệ (chữ cái, số, dấu gạch dưới, dấu chấm)
    clean_user = re.sub(r"[^\w\.]", "", raw).strip(".")
    if clean_user:
        return f"https://www.instagram.com/{clean_user}/"

    return None


def normalize_hotline(val: Optional[str]) -> Optional[Dict[str, str]]:
    """Chuẩn hóa số điện thoại Hotline.
    
    Quy tắc:
    - Tạo đường dẫn gọi điện dạng tel:{phone}.
    - Giữ nguyên định dạng số điện thoại người dùng nhập để hiển thị.
    - Làm sạch số để đưa vào thuộc tính href (bỏ dấu cách, dấu gạch ngang, dấu chấm).
    """
    raw = clean_string(val)
    if not raw or raw in ("#", "/"):
        return None

    # Giữ nguyên số hiển thị
    display = raw

    # Tạo chuỗi số gọi điện thoại
    clean_digits = re.sub(r"[^\d\+]", "", raw)
    if not clean_digits:
        return None

    return {
        "display": display,
        "href": f"tel:{clean_digits}",
    }


def build_cta_context(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Xây dựng đối tượng dữ liệu CTA tổng hợp cho Jinja2 templates.
    
    Đọc từ dict dữ liệu chiến dịch, chuẩn hóa từng kênh và trả về danh sách
    nút CTA hợp lệ để template render linh hoạt mà không bị khoảng trắng thừa.
    """
    messenger_raw = raw_data.get("messenger_link") or raw_data.get("facebook_url")
    tiktok_shop_raw = raw_data.get("tiktok_shop_link") or raw_data.get("tiktok_url")
    zalo_raw = raw_data.get("zalo_link") or raw_data.get("social_zalo")
    instagram_raw = raw_data.get("instagram_link") or raw_data.get("instagram_url") or raw_data.get("social_instagram")
    hotline_raw = raw_data.get("hotline") or raw_data.get("hotline_number")

    messenger_url = normalize_messenger(messenger_raw)
    tiktok_shop_url = normalize_tiktok_shop(tiktok_shop_raw)
    zalo_url = normalize_zalo(zalo_raw)
    instagram_url = normalize_instagram(instagram_raw)
    hotline_info = normalize_hotline(hotline_raw)

    items: List[Dict[str, str]] = []

    if messenger_url:
        items.append({
            "key": "messenger",
            "name": "Messenger",
            "href": messenger_url,
            "display": "Chat Messenger",
            "icon_type": "messenger",
            "color_bg": "bg-[#0084FF] text-white hover:bg-[#0073e6]",
            "border_color": "border-[#0084FF]/30",
        })

    if tiktok_shop_url:
        items.append({
            "key": "tiktok_shop",
            "name": "TikTok Shop",
            "href": tiktok_shop_url,
            "display": "TikTok Shop",
            "icon_type": "tiktok",
            "color_bg": "bg-black text-white hover:bg-stone-800",
            "border_color": "border-black/20",
        })

    if zalo_url:
        items.append({
            "key": "zalo",
            "name": "Zalo",
            "href": zalo_url,
            "display": "Zalo Official",
            "icon_type": "zalo",
            "color_bg": "bg-[#0068FF] text-white hover:bg-[#005ce6]",
            "border_color": "border-[#0068FF]/30",
        })

    if instagram_url:
        items.append({
            "key": "instagram",
            "name": "Instagram",
            "href": instagram_url,
            "display": "Instagram",
            "icon_type": "instagram",
            "color_bg": "bg-gradient-to-tr from-[#f09433] via-[#dc2743] to-[#bc1888] text-white hover:opacity-90",
            "border_color": "border-pink-500/30",
        })

    if hotline_info:
        items.append({
            "key": "hotline",
            "name": "Hotline",
            "href": hotline_info["href"],
            "display": hotline_info["display"],
            "icon_type": "hotline",
            "color_bg": "bg-emerald-600 text-white hover:bg-emerald-700",
            "border_color": "border-emerald-600/30",
        })

    has_any = len(items) > 0

    return {
        "has_any_cta": has_any,
        "items": items,
        "count": len(items),
        "messenger_link": messenger_url,
        "tiktok_shop_link": tiktok_shop_url,
        "zalo_link": zalo_url,
        "instagram_link": instagram_url,
        "hotline": hotline_info["display"] if hotline_info else None,
        "hotline_href": hotline_info["href"] if hotline_info else None,
    }
