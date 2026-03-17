# Use an official Python runtime with Playwright dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY shoe-deal-bot/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY shoe-deal-bot/ .

# Ensure the logs and data directories exist
RUN mkdir -p logs data

# Expose no ports (standard for a bot)
# Define environment variable for any secrets if needed (optional, config.json used here)

# Run the bot
CMD ["python3", "main.py"]
