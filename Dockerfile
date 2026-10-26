FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết (nếu có)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/dist
COPY --from=frontend-build /frontend/dist-mcp ./frontend/dist-mcp

EXPOSE 4789 4790

# Chạy ứng dụng bằng gunicorn với cấu hình tối ưu
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
