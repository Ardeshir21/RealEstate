# Use a specific Python version
FROM python:3.10.11

# Set the working directory
WORKDIR /app

# Set the environment variable to prevent .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements.txt into the container
COPY requirements.txt ./

# Install any dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port that the app will run on
EXPOSE 8000

# Command to run the application (can be overridden in docker-compose.yml)
CMD ["gunicorn", "RealEstate.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--reload"]

