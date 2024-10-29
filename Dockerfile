# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install system dependencies for MySQL and Tkinter (which is required for GUI in tkinter)
RUN apt-get update && apt-get install -y \
    python3-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-tk

# Install any Python dependencies specified in requirements.txt
RUN pip install --no-cache-dir mysql-connector-python requests

# Expose the port the app runs on (5000 is used as an example, adjust based on actual app configuration)
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]

