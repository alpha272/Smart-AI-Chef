import gradio as gr

def generate_recipe(image, additional_ingredients):
    if image is None and not additional_ingredients:
        return "Vui lòng tải ảnh nguyên liệu lên hoặc nhập tên nguyên liệu!"
    
    res = "🍳 **GỢI Ý CÔNG THỨC NẤU ĂN DEMO**\n\n"
    res += "1. **Món đề xuất:** Trứng chiên cà chua & Thịt xào rau củ\n"
    res += "2. **Nguyên liệu phát hiện:** Cà chua, Trứng gà, Hành lá\n"
    res += "3. **Hướng dẫn sơ chế:** Rửa sạch cà chua, thái múi cau. Đánh tan trứng gà với ít gia vị.\n"
    res += "4. **Các bước thực hiện:** Phi thơm hành, cho cà chua vào xào mềm, đổ trứng vào đảo đều..."
    return res

with gr.Blocks(title="Smart AI Chef") as demo:
    gr.Markdown("# 🍳 Smart AI Chef - Gợi ý món ăn thông minh")
    gr.Markdown("Tải ảnh nguyên liệu trong bếp hoặc nhập thêm nguyên liệu để AI gợi ý công thức nấu ăn!")
    
    with gr.Row():
        with gr.Column():
            img_input = gr.Image(type="pil", label="Tải ảnh nguyên liệu")
            text_input = gr.Textbox(placeholder="VD: Cần tây, thịt bò, tỏi...", label="Nhập thêm nguyên liệu (nếu có)")
            submit_btn = gr.Button("🔍 Gợi ý công thức", variant="primary")
        
        with gr.Column():
            output_text = gr.Markdown(label="Công thức đề xuất")
            
    submit_btn.click(fn=generate_recipe, inputs=[img_input, text_input], outputs=output_text)

if __name__ == "__main__":
   demo.launch(share=True)