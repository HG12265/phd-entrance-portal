FROM node:20-alpine

WORKDIR /app

# Copy package configurations
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Expose Vite default dev port
EXPOSE 5173

# Run Vite dev server with host flag to allow network mapping
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
