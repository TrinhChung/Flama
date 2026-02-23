FROM python:3.11-slim

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết (nếu có)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . .

EXPOSE 5000

# Chạy ứng dụng bằng gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
