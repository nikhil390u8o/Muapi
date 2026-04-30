FROM node:18

# Python और yt-dlp इंस्टॉल करें
RUN apt-get update && apt-get install -y python3 python3-pip curl
RUN curl -L https://github.com -o /usr/local/bin/yt-dlp
RUN chmod a+rx /usr/local/bin/yt-dlp

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# Render डायनेमिक पोर्ट देता है
ENV PORT=10000
EXPOSE 10000

CMD ["node", "server.js"]
