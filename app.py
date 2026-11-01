
import os
import io
import re
import html
import requests
import markdown
import bleach

from flask import Flask, render_template, request
from google import genai
from PIL import Image
from dotenv import load_dotenv


# ==============================
# 1. LOAD API KEY
# ==============================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")

MODEL_NAME = "gemini-3.5-flash-lite"

if not API_KEY:
    raise ValueError("Không tìm thấy GEMINI_API_KEY trong file .env")

if not UNSPLASH_ACCESS_KEY:
    raise ValueError("Không tìm thấy UNSPLASH_ACCESS_KEY trong file .env")

client = genai.Client(api_key=API_KEY)


# ==============================
# 2. FLASK CONFIGURATION
# ==============================

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

MAX_IMAGES = 5


# ==============================
# 3. SEARCH FOOD IMAGE
# ==============================

def tim_anh_mon_an(ten_mon):

    url = "https://api.unsplash.com/search/photos"

    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"
    }

    params = {
        "query": ten_mon + " food",
        "per_page": 1,
        "orientation": "landscape"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if not data.get("results"):
            return None

        photo = data["results"][0]

        return {
            "image_url": photo["urls"]["regular"],
            "photo_url": photo["links"]["html"],
            "author": photo["user"]["name"],
            "author_url": photo["user"]["links"]["html"]
        }

    except requests.RequestException as e:
        print("UNSPLASH ERROR:", e)
        return None

    except (KeyError, IndexError, ValueError) as e:
        print("IMAGE DATA ERROR:", e)
        return None


# ==============================
# 4. FORMAT AI RESULT
# ==============================

def dinh_dang_ket_qua(noi_dung):

    html_result = markdown.markdown(
        noi_dung,
        extensions=["extra", "nl2br"]
    )

    # Tìm tiêu đề các món ăn
    def chen_anh(match):

        ten_mon = html.unescape(
            re.sub(r"<.*?>", "", match.group(1))
        ).strip()

        # Bỏ qua tiêu đề không phải tên món ăn
        if not ten_mon or ten_mon.lower() in [
            "tên món ăn",
            "nguyên liệu cần thiết",
            "cách chế biến",
            "mẹo nấu ăn",
            "nguyên liệu nhận diện",
            "gợi ý món ăn",
            "nguyên liệu thay thế"
        ]:
            return match.group(0)

        # Tìm ảnh trên Unsplash
        anh = tim_anh_mon_an(ten_mon)

        if not anh:
            return match.group(0)

        # Tạo HTML ảnh và nguồn ảnh
        the_anh = f"""
        <div class="food-image">
            <img
                src="{html.escape(anh['image_url'], quote=True)}"
                alt="{html.escape(ten_mon, quote=True)}"
                loading="lazy"
            >
            <p class="image-credit">
                Ảnh bởi
                <a href="{html.escape(anh['author_url'], quote=True)}?utm_source=AI_Chef&utm_medium=referral">
                    {html.escape(anh['author'])}
                </a>
                trên
                <a href="{html.escape(anh['photo_url'], quote=True)}?utm_source=AI_Chef&utm_medium=referral">
                    Unsplash
                </a>
            </p>
        </div>
        """

        return match.group(0) + the_anh

    # Chèn ảnh vào tối đa 3 tiêu đề h3
    dem = 0

    def xu_ly_tieu_de(match):
        nonlocal dem

        if dem >= 3:
            return match.group(0)

        ket_qua = chen_anh(match)

        if ket_qua != match.group(0):
            dem += 1

        return ket_qua

    html_result = re.sub(
        r"<h3>(.*?)</h3>",
        xu_ly_tieu_de,
        html_result,
        flags=re.IGNORECASE
    )

    # Cho phép các thẻ cần thiết
    allowed_tags = set(bleach.sanitizer.ALLOWED_TAGS).union({
        "p", "h1", "h2", "h3",
        "ul", "ol", "li",
        "strong", "em",
        "table", "thead", "tbody",
        "tr", "th", "td",
        "hr", "br",
        "div", "img", "a"
    })

    allowed_attributes = {
        "img": ["src", "alt", "loading"],
        "a": ["href"],
        "div": ["class"],
        "p": ["class"]
    }

    return bleach.clean(
        html_result,
        tags=allowed_tags,
        attributes=allowed_attributes,
        protocols=["http", "https"],
        strip=True
    )


# ==============================
# 5. GENERATE RECIPE WITH GEMINI
# ==============================

def goi_y_mon_an(
    danh_sach_anh,
    nguyen_lieu_them,
    khau_phan,
    danh_muc,
    nguyen_lieu_thay_the,
    yeu_cau
):

    prompt = f"""
Bạn là AI Chef, trợ lý nấu ăn bằng tiếng Việt.

NHIỆM VỤ:
Phân tích tất cả hình ảnh nguyên liệu người dùng cung cấp.
Nhận diện những nguyên liệu có thể nhìn thấy trong ảnh.
Không khẳng định chắc chắn nếu hình ảnh không rõ.

THÔNG TIN NGƯỜI DÙNG:

- Nguyên liệu bổ sung: {nguyen_lieu_them or "Không có"}
- Số người ăn: {khau_phan}
- Danh mục món ăn: {danh_muc}
- Nguyên liệu muốn thay thế: {nguyen_lieu_thay_the or "Không có"}
- Yêu cầu thêm: {yeu_cau or "Không có"}

YÊU CẦU VỀ DANH MỤC:

- Nếu người dùng chọn "Tất cả món ăn",
  hãy tự do đề xuất những món phù hợp với nguyên liệu.
- Nếu người dùng chọn danh mục cụ thể,
  tất cả món được đề xuất phải thuộc danh mục đó.
- Không đề xuất món nằm ngoài danh mục đã chọn.

YÊU CẦU VỀ THAY THẾ NGUYÊN LIỆU:

- Nếu người dùng nhập nguyên liệu muốn thay thế,
  hãy đề xuất từ 2 đến 3 nguyên liệu thay thế phù hợp.
- Giải thích vì sao có thể sử dụng nguyên liệu thay thế đó.
- Đưa ra lượng sử dụng tham khảo tương ứng với nguyên liệu ban đầu.
- Nêu rõ sự khác biệt về hương vị, kết cấu hoặc cách chế biến.
- Nếu không có nguyên liệu thay thế phù hợp,
  hãy nói rõ thay vì đưa ra gợi ý không an toàn hoặc không hợp lý.
- Nếu người dùng không nhập nguyên liệu muốn thay thế,
  không cần tạo phần thay thế.

YÊU CẦU ĐẦU RA:

## 1. Nguyên liệu nhận diện

Liệt kê những nguyên liệu nhìn thấy trong ảnh.
Phân biệt nguyên liệu chắc chắn và nguyên liệu chưa rõ.

## 2. Gợi ý món ăn

Đề xuất tối đa 3 món phù hợp với nguyên liệu
và danh mục đã chọn.

Với mỗi món, trình bày:

### Tên món ăn
- Mô tả ngắn.
- Mức độ khó.
- Thời gian chuẩn bị và nấu.

### Nguyên liệu cần thiết
Liệt kê nguyên liệu và định lượng phù hợp với {khau_phan}.

### Cách chế biến
Hướng dẫn từng bước rõ ràng, dễ thực hiện.

### Mẹo nấu ăn
Đưa ra một vài mẹo giúp món ăn ngon hơn.

## 3. Nguyên liệu thay thế

Chỉ hiển thị phần này nếu người dùng có nhập
nguyên liệu muốn thay thế.

Trình bày:
- Nguyên liệu ban đầu.
- Các nguyên liệu có thể thay thế.
- Tỉ lệ thay thế tham khảo.
- Lưu ý khi sử dụng.

LƯU Ý:
- Ưu tiên tận dụng nguyên liệu người dùng đang có.
- Không tự ý thêm quá nhiều nguyên liệu không cần thiết.
- Hướng dẫn dễ hiểu cho người mới nấu ăn.
- Trả lời hoàn toàn bằng tiếng Việt.
- Với mỗi món ăn, hãy dùng tiêu đề ### với tên món ăn thực tế.
"""

    noi_dung_gui = [prompt] + danh_sach_anh

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=noi_dung_gui
    )

    if not response.text:
        raise ValueError("AI không trả về nội dung.")

    return dinh_dang_ket_qua(response.text)


# ==============================
# 6. MAIN ROUTE
# ==============================

@app.route("/", methods=["GET", "POST"])
def index():

    gia_tri = {
        "nguyen_lieu_them": "",
        "khau_phan": "2 người",
        "danh_muc": "Tất cả món ăn",
        "nguyen_lieu_thay_the": "",
        "yeu_cau": ""
    }

    ket_qua = None
    loi = None

    if request.method == "POST":

        # Get form data

        gia_tri["nguyen_lieu_them"] = request.form.get(
            "nguyen_lieu_them", ""
        )

        gia_tri["khau_phan"] = request.form.get(
            "khau_phan", "2 người"
        )

        gia_tri["danh_muc"] = request.form.get(
            "danh_muc", "Tất cả món ăn"
        )

        gia_tri["nguyen_lieu_thay_the"] = request.form.get(
            "nguyen_lieu_thay_the", ""
        )

        gia_tri["yeu_cau"] = request.form.get(
            "yeu_cau", ""
        )

        # Get uploaded images

        files = request.files.getlist("anh")

        danh_sach_file = [
            file for file in files
            if file and file.filename.strip()
        ]

        if len(danh_sach_file) == 0:

            loi = "Vui lòng tải lên ít nhất một ảnh nguyên liệu."

        elif len(danh_sach_file) > MAX_IMAGES:

            loi = f"Bạn chỉ được tải lên tối đa {MAX_IMAGES} ảnh."

        else:

            danh_sach_anh = []

            try:

                # Validate and load images

                for file in danh_sach_file:

                    image_data = file.read()

                    anh = Image.open(
                        io.BytesIO(image_data)
                    )

                    anh.verify()

                    anh = Image.open(
                        io.BytesIO(image_data)
                    ).convert("RGB")

                    danh_sach_anh.append(anh)

                # Call Gemini

                ket_qua = goi_y_mon_an(
                    danh_sach_anh,
                    gia_tri["nguyen_lieu_them"],
                    gia_tri["khau_phan"],
                    gia_tri["danh_muc"],
                    gia_tri["nguyen_lieu_thay_the"],
                    gia_tri["yeu_cau"]
                )

            except Exception as e:

                print("ERROR:", e)

                loi = (
                    "Đã xảy ra lỗi khi xử lý ảnh hoặc kết nối AI. "
                    "Vui lòng thử lại."
                )

    return render_template(
        "index.html",
        ket_qua=ket_qua,
        loi=loi,
        gia_tri=gia_tri
    )


# ==============================
# 7. FILE TOO LARGE ERROR
# ==============================

@app.errorhandler(413)
def file_too_large(error):

    gia_tri = {
        "nguyen_lieu_them": "",
        "khau_phan": "2 người",
        "danh_muc": "Tất cả món ăn",
        "nguyen_lieu_thay_the": "",
        "yeu_cau": ""
    }

    return render_template(
        "index.html",
        ket_qua=None,
        loi="Tổng dung lượng ảnh vượt quá giới hạn 25MB.",
        gia_tri=gia_tri
    ), 413


# ==============================
# 8. RUN APPLICATION
# ==============================

if __name__ == "__main__":
    app.run(debug=True)
