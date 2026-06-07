FROM node:18-alpine

WORKDIR /app

# Paket dosyalarını kopyala ve kur
COPY package*.json ./
RUN npm install

# Kaynak kodları kopyala
COPY . .

# Vite'in default portu
EXPOSE 5173

# Uygulamayı dev modunda dışarıya açık başlat
CMD ["npm", "run", "dev"]
