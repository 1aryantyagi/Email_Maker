# Use a base Python image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port
EXPOSE 5000

# Run the Flask app
CMD ["python", "app.py"]
