
import os
import io
import markdown
import bleach

from flask import Flask, render_template, request
from google import genai
from PIL import Image
from dotenv import load_dotenv

# =====================================
# 1. CAU HINH GEMINI
# =====================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-3.5-flash-lite"

if not API_KEY:
    raise ValueError("Khong tim thay GEMINI_API_KEY trong file .env")

client = genai.Client(api_key=API_KEY)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


# =====================================
# 2. DINH DANG KET QUA
# =====================================

def dinh_dang_ket_qua(noi_dung):
    html = markdown.markdown(
        noi_dung,
        extensions=["extra", "sane_lists"]
    )

    allowed_tags = bleach.sanitizer.ALLOWED_TAGS.union({
        "p", "h1", "h2", "h3", "h4",
        "ul", "ol", "li", "hr",
        "br", "pre", "code", "blockquote"
    })

    return bleach.clean(
        html,
        tags=allowed_tags,
        strip=True
    )


# =====================================
# 3. GOI GEMINI
# =====================================

def goi_y_mon_an(anh, nguyen_lieu_them, khau_phan, yeu_cau):

    prompt = f"""
Bạn là AI Chef, trợ lý nấu ăn bằng tiếng Việt.

Hãy quan sát ảnh và nhận diện các nguyên liệu nhìn thấy.
Không khẳng định chắc chắn nếu nguyên liệu không rõ.

Nguyên liệu bổ sung:
{nguyen_lieu_them if nguyen_lieu_them else "Không có"}

Số người ăn: {khau_phan}

Yêu cầu thêm:
{yeu_cau if yeu_cau else "Không có"}

Trả lời theo cấu trúc:

## 🥗 1. Nguyên liệu nhận diện
Phân biệt nguyên liệu nhìn thấy và nguyên liệu người dùng cung cấp.

## 🍳 2. Món ăn đề xuất
Đề xuất tối đa 3 món phù hợp.

## 🧂 3. Nguyên liệu cần chuẩn bị
Liệt kê định lượng ước tính cho số người ăn đã chọn.

## 👨‍🍳 4. Cách chế biến
Hướng dẫn từng bước dễ làm.

## ⏱️ 5. Thời gian
Ước tính thời gian chuẩn bị và nấu.

## 💡 6. Mẹo nấu ăn
Đưa ra mẹo hữu ích và lưu ý an toàn thực phẩm.

Trả lời hoàn toàn bằng tiếng Việt.
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[prompt, anh]
    )

    return response.text or "AI chưa tạo được câu trả lời."


# =====================================
# 4. TRANG CHU
# =====================================

@app.route("/", methods=["GET", "POST"])
def index():

    ket_qua = None
    loi = None

    gia_tri = {
        "nguyen_lieu_them": "",
        "khau_phan": "2 người",
        "yeu_cau": ""
    }

    if request.method == "POST":

        file_anh = request.files.get("anh")

        gia_tri["nguyen_lieu_them"] = request.form.get(
            "nguyen_lieu_them", ""
        ).strip()

        gia_tri["khau_phan"] = request.form.get(
            "khau_phan", "2 người"
        )

        gia_tri["yeu_cau"] = request.form.get(
            "yeu_cau", ""
        ).strip()

        if not file_anh or not file_anh.filename:
            loi = "Bạn hãy tải ảnh nguyên liệu lên trước nhé!"

        else:
            try:
                du_lieu_anh = file_anh.read()

                anh = Image.open(
                    io.BytesIO(du_lieu_anh)
                ).convert("RGB")

                noi_dung = goi_y_mon_an(
                    anh,
                    gia_tri["nguyen_lieu_them"],
                    gia_tri["khau_phan"],
                    gia_tri["yeu_cau"]
                )

                ket_qua = dinh_dang_ket_qua(noi_dung)

            except Exception as e:
                loi = f"Không thể phân tích ảnh: {str(e)}"

    return render_template(
        "index.html",
        ket_qua=ket_qua,
        loi=loi,
        gia_tri=gia_tri
    )


# =====================================
# 5. CHAY WEBSITE
# =====================================

if __name__ == "__main__":
    app.run(debug=True)
