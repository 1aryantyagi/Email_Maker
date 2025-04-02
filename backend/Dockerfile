# Use a base Python image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy everything from backend to /app in the container
COPY backend /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Flask runs on
EXPOSE 5000

# Run the Flask app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "backend.app:app"]