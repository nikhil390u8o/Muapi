FROM node:18
RUN apt-get update && apt-get install -y python3 python3-pip curl
RUN curl -L https://github.com -o /usr/local/bin/yt-dlp && chmod a+rx /usr/local/bin/yt-dlp
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ENV PORT=10000
EXPOSE 10000
CMD ["node", "server.js"]
