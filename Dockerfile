FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết (nếu có)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 4789

# Chạy ứng dụng bằng gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:4789", "wsgi:app"]
