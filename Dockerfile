# Stage 1: Builder
# This stage installs dependencies and builds wheels to be used in the runtime stage.
# This helps in keeping the final image size small and build process clean.
FROM python:3.9-slim AS builder

WORKDIR /app

# Install git and build tools to allow cloning from git repositories and compiling C extensions
RUN apt-get update && apt-get install -y git build-essential --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install a compatible version of numpy first to avoid compilation issues with dependencies like newtulipy
RUN pip install --no-cache-dir "numpy<1.23"

# Copy only the requirements file to leverage Docker's layer caching
COPY requirements.txt .

# Build wheels for all dependencies
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# Stage 2: Runtime
# This stage creates the final production-ready image.
FROM python:3.9-slim

# Set environment variables for a cleaner and more predictable output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install git to allow installing dependencies from git repositories
RUN apt-get update && apt-get install -y git --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for security purposes
# Running containers as a non-root user is a security best practice
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Copy the pre-built wheels from the builder stage
COPY --from=builder /wheels /wheels
# Copy the requirements file
COPY --from=builder /app/requirements.txt .

# Install the dependencies from the wheels using the requirements file
# This ensures that pip resolves dependencies correctly from the local wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

# Copy the application source code
COPY ./app /app/app

# Change the ownership of the application directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Use an environment variable for the port, with a default value
ENV PORT=8002

# Expose the port that the application will run on
EXPOSE $PORT

# Command to run the application using Gunicorn with Uvicorn workers
# Using sh -c allows for environment variable substitution while using the recommended exec form.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:$PORT --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app"]
