#Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the content of the current directory to the container
COPY ./app /app

# Use an environment variable for the port, with a default value
ENV PORT 8002

# Expose the port defined by the environment variable
EXPOSE $PORT

# Run main.py when the container launches
# Use shell form for CMD to allow environment variable substitution
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT