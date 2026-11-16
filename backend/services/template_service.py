"""Service render HTML cho Landing Page.

Hỗ trợ render HTML hoàn chỉnh từ thông tin project (text, giá, link social, color theme, ảnh...).
Sử dụng Tailwind CSS CDN để tạo giao diện responsive, hiện đại, xem trước tức thì.
"""

from __future__ import annotations

import html
import json
from typing import Any


def _format_price(price: float | int | str | None) -> str:
    """Định dạng giá tiền hiển thị kiểu VND (e.g. 500.000 ₫)."""
    if price is None:
        return ""
    try:
        val = float(price)
        if val == int(val):
            val = int(val)
        return f"{val:,.0f} ₫".replace(",", ".")
    except (ValueError, TypeError):
        return str(price)


def render_landing_page(project: dict[str, Any]) -> str:
    """Render mã HTML đầy đủ cho landing page dựa trên thông tin project.

    Args:
        project: Dict chứa thông tin project:
            - campaign_name
            - product_name
            - product_description
            - price
            - image_url
            - color_theme
            - facebook_url
            - tiktok_url
            - instagram_url
            - raw_json_data (optional dict/str)

    Returns:
        Chuỗi HTML hợp lệ, standalone.
    """
    raw_json = project.get("raw_json_data")
    if isinstance(raw_json, str):
        try:
            raw_data = json.loads(raw_json)
        except Exception:
            raw_data = {}
    elif isinstance(raw_json, dict):
        raw_data = raw_json
    else:
        raw_data = {}

    campaign_name = html.escape(str(project.get("campaign_name") or "Chiến dịch Landing Page"))
    product_name = html.escape(str(project.get("product_name") or "Sản phẩm nổi bật"))
    product_desc = html.escape(
        str(project.get("product_description") or "Trải nghiệm sản phẩm tuyệt vời với chất lượng vượt trội.")
    )
    price_val = project.get("price")
    formatted_price = _format_price(price_val)

    color_theme = project.get("color_theme") or "#6366f1"  # Default Indigo
    # Sanitize color_theme hex
    if not color_theme.startswith("#"):
        color_theme = f"#{color_theme}"
    # Valid hex check
    if len(color_theme) not in (4, 7):
        color_theme = "#6366f1"

    image_url = project.get("image_url") or ""
    if not image_url.strip():
        # Fallback placeholder image
        image_url = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80"
    image_url = html.escape(image_url)

    facebook_url = project.get("facebook_url") or ""
    tiktok_url = project.get("tiktok_url") or ""
    instagram_url = project.get("instagram_url") or ""

    headline = html.escape(str(raw_data.get("headline") or product_name))
    subheadline = html.escape(
        str(raw_data.get("subheadline") or "Giải pháp hoàn hảo được thiết kế riêng cho phong cách của bạn.")
    )
    cta_text = html.escape(str(raw_data.get("cta_text") or "Đặt Mua Ngay"))

    # Features list from raw_data if provided
    features = raw_data.get("features")
    if not isinstance(features, list) or not features:
        features = [
            {"title": "Chất lượng cao cấp", "desc": "Cam kết vật liệu chuẩn loại 1, bền bỉ theo thời gian."},
            {"title": "Giao hàng siêu tốc", "desc": "Nhận hàng nhanh chóng trên toàn quốc, kiểm tra trước khi nhận."},
            {"title": "Bảo hành uy tín", "desc": "Hỗ trợ 1 đổi 1 trong 30 ngày nếu phát sinh lỗi từ nhà sản xuất."},
        ]

    features_html = ""
    for idx, feat in enumerate(features, 1):
        f_title = html.escape(str(feat.get("title", f"Tính năng nổi bật {idx}")))
        f_desc = html.escape(str(feat.get("desc", "")))
        features_html += f"""
        <div class="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow border border-slate-100 flex flex-col justify-between">
            <div>
                <div class="w-12 h-12 rounded-xl flex items-center justify-center text-white mb-4 font-bold text-lg shadow-sm" style="background-color: {color_theme};">
                    0{idx}
                </div>
                <h3 class="text-xl font-bold text-slate-800 mb-2">{f_title}</h3>
                <p class="text-slate-600 leading-relaxed text-sm">{f_desc}</p>
            </div>
        </div>
        """

    # Social links HTML
    social_links_html = ""
    if facebook_url:
        social_links_html += f"""
        <a href="{html.escape(facebook_url)}" target="_blank" rel="noopener noreferrer" 
           class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 font-medium text-sm transition-colors">
            <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
            Facebook
        </a>
        """
    if tiktok_url:
        social_links_html += f"""
        <a href="{html.escape(tiktok_url)}" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-900 text-white hover:bg-slate-800 font-medium text-sm transition-colors">
            <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.97-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.24 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/></svg>
            TikTok
        </a>
        """
    if instagram_url:
        social_links_html += f"""
        <a href="{html.escape(instagram_url)}" target="_blank" rel="noopener noreferrer"
           class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-pink-50 text-pink-600 hover:bg-pink-100 font-medium text-sm transition-colors">
            <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/></svg>
            Instagram
        </a>
        """

    price_badge_html = ""
    if formatted_price:
        price_badge_html = f"""
        <div class="inline-flex items-baseline gap-2 bg-slate-900/5 px-4 py-2 rounded-xl mb-6">
            <span class="text-sm font-semibold uppercase tracking-wider text-slate-500">Giá ưu đãi:</span>
            <span class="text-3xl font-extrabold text-slate-900">{formatted_price}</span>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="vi" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{product_name} - {campaign_name}</title>
    <meta name="description" content="{product_desc}">
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        .brand-accent {{
            color: {color_theme};
        }}
        .bg-brand {{
            background-color: {color_theme};
        }}
        .border-brand {{
            border-color: {color_theme};
        }}
    </style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased selection:bg-indigo-500 selection:text-white">

    <!-- Navbar -->
    <nav class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-100">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center text-white font-black text-sm bg-brand shadow-sm">
                    {product_name[:1].upper()}
                </div>
                <span class="font-bold text-lg text-slate-900 tracking-tight">{product_name}</span>
            </div>
            <div class="flex items-center gap-4">
                <a href="#order-section" class="px-5 py-2 rounded-xl text-white font-medium text-sm shadow-md transition-all hover:opacity-95 hover:shadow-lg bg-brand">
                    {cta_text}
                </a>
            </div>
        </div>
    </nav>

    <!-- Hero Section -->
    <header class="relative overflow-hidden pt-12 pb-20 lg:pt-20 lg:pb-28">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
                
                <!-- Left text content -->
                <div class="lg:col-span-7 space-y-6">
                    <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider border border-brand/20 bg-brand/10 brand-accent">
                        <span>✨ {campaign_name}</span>
                    </div>

                    <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-950 tracking-tight leading-[1.15]">
                        {headline}
                    </h1>

                    <p class="text-lg text-slate-600 leading-relaxed max-w-xl">
                        {product_desc}
                    </p>

                    {price_badge_html}

                    <div class="flex flex-wrap items-center gap-4 pt-2" id="order-section">
                        <a href="#contact" class="px-8 py-3.5 rounded-2xl text-white font-semibold text-base shadow-lg shadow-indigo-500/20 hover:shadow-xl hover:opacity-95 transition-all bg-brand">
                            {cta_text}
                        </a>
                        <a href="#features" class="px-6 py-3.5 rounded-2xl bg-white text-slate-700 font-semibold text-base border border-slate-200 hover:bg-slate-50 transition-colors shadow-sm">
                            Tìm hiểu thêm
                        </a>
                    </div>
                </div>

                <!-- Right image content -->
                <div class="lg:col-span-5 relative">
                    <div class="relative mx-auto max-w-md rounded-3xl overflow-hidden shadow-2xl border-4 border-white bg-white group">
                        <img src="{image_url}" alt="{product_name}" class="w-full h-80 sm:h-96 object-cover object-center group-hover:scale-105 transition-transform duration-500" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80'">
                        <div class="absolute inset-0 bg-gradient-to-t from-slate-950/60 via-transparent to-transparent"></div>
                        <div class="absolute bottom-4 left-4 right-4 text-white p-2">
                            <p class="text-xs font-semibold uppercase tracking-wider text-slate-200">Sản phẩm chính hãng</p>
                            <p class="text-lg font-bold truncate">{product_name}</p>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </header>

    <!-- Features Section -->
    <section id="features" class="py-16 bg-slate-100/70 border-t border-slate-200/60">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="text-center max-w-2xl mx-auto mb-12">
                <h2 class="text-xs font-bold uppercase tracking-widest brand-accent mb-2">Ưu điểm vượt trội</h2>
                <h3 class="text-3xl font-extrabold text-slate-950 tracking-tight">Tại sao bạn nên chọn {product_name}?</h3>
                <p class="mt-3 text-slate-600 text-sm leading-relaxed">{subheadline}</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {features_html}
            </div>
        </div>
    </section>

    <!-- Call to action banner -->
    <section class="py-16 bg-white border-t border-slate-200/60">
        <div class="max-w-4xl mx-auto px-4 text-center">
            <div class="p-8 sm:p-12 rounded-3xl bg-slate-900 text-white shadow-xl relative overflow-hidden">
                <div class="relative z-10 space-y-4">
                    <h3 class="text-2xl sm:text-4xl font-extrabold tracking-tight">Sở hữu {product_name} ngay hôm nay!</h3>
                    <p class="text-slate-300 max-w-xl mx-auto text-sm sm:text-base leading-relaxed">
                        Đừng bỏ lỡ ưu đãi đặc biệt trong chiến dịch {campaign_name}. Số lượng có hạn!
                    </p>
                    <div class="pt-4">
                        <button class="px-8 py-3.5 rounded-2xl text-white font-bold text-base shadow-lg hover:opacity-95 transition-all bg-brand">
                            {cta_text}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer & Social Links -->
    <footer id="contact" class="bg-white border-t border-slate-200 py-12">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
            <div class="flex items-center justify-center gap-3">
                <div class="w-7 h-7 rounded-lg flex items-center justify-center text-white font-bold text-xs bg-brand">
                    {product_name[:1].upper()}
                </div>
                <span class="font-bold text-base text-slate-900">{product_name}</span>
            </div>

            <p class="text-slate-500 text-sm max-w-md mx-auto">
                Kết nối với chúng tôi qua các kênh mạng xã hội để cập nhật tin tức và ưu đãi mới nhất.
            </p>

            <div class="flex flex-wrap items-center justify-center gap-3 pt-2">
                {social_links_html if social_links_html else '<span class="text-xs text-slate-400">Chưa thiết lập link mạng xã hội</span>'}
            </div>

            <div class="pt-6 border-t border-slate-100 text-slate-400 text-xs">
                © 2026 {product_name}. Powered by AI Auto Landing Page Publisher.
            </div>
        </div>
    </footer>

</body>
</html>
"""
    return html_content
