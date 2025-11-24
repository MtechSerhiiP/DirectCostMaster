# Deployment Instructions for Direct Cost Master on DigitalOcean

This guide will walk you through deploying the Direct Cost Master application on a DigitalOcean Droplet using Docker.

## Prerequisites

1.  **DigitalOcean Account**: You'll need an account to create Droplets.
2.  **Docker Hub Account**: To store your Docker images.
3.  **Git**: To push your code to a repository.
4.  **A code repository**: (e.g., GitHub, GitLab) to host your application code.

## Step 1: Prepare Your Local Environment

1.  **Install Docker**: Make sure you have Docker and Docker Compose installed on your local machine.
2.  **Push to Git**: Push your application code, including the `Dockerfile`s and `docker-compose.yml`, to your Git repository.

## Step 2: Build and Push Docker Images to Docker Hub

1.  **Login to Docker Hub**:
    ```bash
    docker login
    ```

2.  **Build the server image**:
    ```bash
    docker build -f server/Dockerfile -t YOUR_DOCKERHUB_USERNAME/direct-cost-master-server:latest .
    ```

3.  **Build the client image**:
    ```bash
    docker build -f client/Dockerfile -t YOUR_DOCKERHUB_USERNAME/direct-cost-master-client:latest .
    ```

4.  **Push the server image**:
    ```bash
    docker push YOUR_DOCKERHUB_USERNAME/direct-cost-master-server:latest
    ```

5.  **Push the client image**:
    ```bash
    docker push YOUR_DOCKERHUB_USERNAME/direct-cost-master-client:latest
    ```

## Step 3: Set Up a DigitalOcean Droplet

1.  **Create a Droplet**:
    *   Go to your DigitalOcean dashboard and click "Create" -> "Droplets".
    *   Choose an image: Select the **Docker** image from the Marketplace tab. This will give you a server with Docker pre-installed.
    *   Choose a plan: A basic plan should be sufficient to start.
    *   Choose a datacenter region: Pick one closest to your users.
    *   Authentication: Select **SSH keys** for better security. Add your public SSH key.
    *   Choose a hostname: e.g., `direct-cost-master`.
    *   Click "Create Droplet".

2.  **Connect to your Droplet**:
    Once the Droplet is created, copy its IP address. Connect to it via SSH:
    ```bash
    ssh root@YOUR_DROPLET_IP
    ```

## Step 4: Deploy the Application on the Droplet

1.  **Clone your repository**:
    ```bash
    git clone YOUR_GIT_REPOSITORY_URL
    cd YOUR_PROJECT_DIRECTORY
    ```

2.  **Update `docker-compose.yml`**:
    You need to modify the `docker-compose.yml` to use the images you pushed to Docker Hub.

    ```yaml
    version: '3.8'

    services:
      server:
        image: YOUR_DOCKERHUB_USERNAME/direct-cost-master-server:latest
        ports:
          - "8000:8000"
        volumes:
          - ./server/temp_files:/app/temp_files
          - ./server/temp_exports:/app/temp_exports
          - ./auth.db:/app/auth.db
        networks:
          - app-network

      client:
        image: YOUR_DOCKERHUB_USERNAME/direct-cost-master-client:latest
        ports:
          - "8080:8080"
        depends_on:
          - server
        networks:
          - app-network

    networks:
      app-network:
        driver: bridge
    ```
    *   Replace `YOUR_DOCKERHUB_USERNAME` with your actual Docker Hub username.
    *   You can use a text editor like `nano` to edit the file: `nano docker-compose.yml`.

3.  **Run the application**:
    Use Docker Compose to pull the images and start the containers:
    ```bash
    docker-compose pull
    docker-compose up -d
    ```
    The `-d` flag runs the containers in detached mode.

## Step 5: Access Your Application

*   **API Server**: Your FastAPI server will be accessible at `http://YOUR_DROPLET_IP:8000`.
*   **Client Application**: Your NiceGUI client will be accessible at `http://YOUR_DROPLET_IP:8080`.

## Step 6: (Optional) Set Up a Domain and HTTPS

For a production environment, you should:

1.  **Point a domain name** to your Droplet's IP address.
2.  **Set up a reverse proxy** (like Nginx or Caddy) to manage traffic to your Docker containers.
3.  **Secure your application with an SSL certificate** (e.g., using Let's Encrypt).

This setup will allow you to access your client at a standard domain (e.g., `https://your-app-domain.com`) without needing to specify the port.

## Managing Your Deployment

*   **View logs**:
    ```bash
    docker-compose logs -f
    ```
*   **Stop the application**:
    ```bash
    docker-compose down
    ```
*   **Update the application**:
    1.  Push new images to Docker Hub.
    2.  On the Droplet, pull the latest images and restart the containers:
        ```bash
        docker-compose pull
        docker-compose up -d
        ```
