## Maintainance of EC2 server

```
[ec2-user@ip-172-31-42-109 ~]$ docker ps -a
CONTAINER ID   IMAGE                                                                             COMMAND                  CREATED        STATUS        PORTS                                                           NAMES
a0b7e5115b81   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-proxy:latest      "docker-entrypoint.s…"   38 hours ago   Up 38 hours   0.0.0.0:4000->4000/tcp, :::4000->4000/tcp                       workflow-proxy
6913553c4efb   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-frontend:latest   "/docker-entrypoint.…"   38 hours ago   Up 38 hours   0.0.0.0:3000->80/tcp, :::3000->80/tcp                           workflow-frontend
0ee59b1ccb71   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-backend:latest    "sh -c 'uvicorn src.…"   38 hours ago   Up 38 hours   0.0.0.0:5958-5959->5958-5959/tcp, :::5958-5959->5958-5959/tcp   workflow-backend
```

Server logs:

```
docker logs workflow-backend
```