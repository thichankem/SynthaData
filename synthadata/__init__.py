"""SynthaData - bộ sinh dữ liệu tổng hợp (synthetic tabular data) chất lượng cao.

Kiến trúc nhiều lớp:
    config      -> cấu hình
    schema      -> định nghĩa domain / cột
    providers   -> nguồn LLM (API ngoài hoặc Ollama offline)
    prompts     -> dựng prompt
    generator   -> điều phối sinh dữ liệu song song
    validation  -> kiểm tra chất lượng liên tục (dedup, làm sạch, validate)
    writer      -> ghi CSV + checkpoint
"""

__version__ = "1.0.0"
