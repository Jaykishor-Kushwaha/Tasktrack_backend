# Use the official Python image as a base image
FROM python:3.9-alpine

# Install system dependencies
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    postgresql-dev \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev

# Set the working directory inside the container
WORKDIR /app

# Copy only the necessary files and directories into the container
COPY task_trak /app/task_trak
COPY requirements.txt /app/
COPY run.py /app/

# Create a virtual environment and install dependencies
RUN python -m venv venv
RUN /app/venv/bin/pip install -r requirements.txt

# Create a build argument for the tag
ARG TAG

# Expose the port your Flask app will run on (usually it's 5000)
EXPOSE 5000

# Define the command to run your Flask app
CMD ["/app/venv/bin/python", "-m", "run"]

# Add a label to the image with the specified tag
LABEL version="${TAG}"

