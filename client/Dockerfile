# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY ./client/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the client application code
COPY ./client /app/

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application
CMD ["python", "main.py"]
