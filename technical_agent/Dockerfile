# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Expose port 8002 to the Docker host
EXPOSE 8002

# Command to run the application on port 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
