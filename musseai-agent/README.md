## Deployment on test server

### Add custom network on docker

```shell
sudo docker network create musseai_network
```

### Add redis-ml and mysql to custom network

```shell
sudo docker network connect redis-ml musseai_network

sudo docker network connect mysql musseai_network
```

### Use custom network in `docker-compose-test.yaml`

```yaml
volumes:
    langgraph-data:
        driver: local
    langgraph_api_data:
        driver: local

services:
    langgraph-postgres:
        image: postgres:16
        ports:
            - "5433:5432"
        environment:
            POSTGRES_DB: postgres
            POSTGRES_USER: postgres
            POSTGRES_PASSWORD: postgres
        volumes:
            - langgraph-data:/var/lib/postgresql/data
        healthcheck:
            test: pg_isready -U postgres
            start_period: 10s
            timeout: 1s
            retries: 5
            interval: 5s
        networks:
            - musseai_network
    
    langgraph-api:
        image: musseai-agent
        ports:
            - "8123:8000"
        depends_on:
            langgraph-postgres:
                condition: service_healthy
        env_file:
            - .env
        extra_hosts:
            - "host.docker.internal:host-gateway"
        networks:
            - default
        volumes:
            - langgraph_api_data:/logs/
            - ./chromedriver-linux64:/chromedriver-linux64
        # Chrome运行所需的安全配置
        security_opt:
            - seccomp:unconfined
        shm_size: 2gb
        cap_add:
            - SYS_ADMIN
        networks:
            - musseai_network
networks:
    musseai_network:
        external: true
```

### Init database

Find out mysql's container name.

```shell
sudo docker ps

CONTAINER ID   IMAGE           COMMAND                  CREATED          STATUS                    PORTS                                                  NAMES
050f30824fcf   php:5.6-fpm     "docker-php-entrypoi…"   3 months ago     Up 3 months               0.0.0.0:9099->9000/tcp, [::]:9099->9000/tcp            php5.6-fpm
d0c24f5527cb   redis           "docker-entrypoint.s…"   13 months ago    Up 3 months               0.0.0.0:6389->6379/tcp, [::]:6389->6379/tcp            redis-ml
ffd9adc61ce2   mysql:8.0       "docker-entrypoint.s…"   17 months ago    Up 5 months               0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp   mysql
4ec122aeda86   qdrant/qdrant   "./entrypoint.sh"        18 months ago    Up 5 months               0.0.0.0:6333->6333/tcp, :::6333->6333/tcp, 6334/tcp    qdrant_container
```

Copy sql file to mysql container

```shell
sudo docker cp ./src/mysql/crypto_portfolio.sql mysql:/tmp/
sudo docker cp ./src/mysql/insert_assets_cp.sql mysql:/tmp/
sudo docker cp ./src/mysql/auth.sql mysql:/tmp/
```

Access the bash of mysql's container.

```shell
sudo docker exec -it mysql bash
```

Access mysql

```shell
mysql -uroot -p
password:
```

Execute sql files.

```sql
source /tmp/crypto_portfolio.sql
source /tmp/auth.sql
source /tmp/insert_assets_cp.sql
```

### Use the container name to connect redis or mysql in `.env`

Find out the container name of mysql and redis.

```shell
sudo docker ps

CONTAINER ID   IMAGE           COMMAND                  CREATED          STATUS                    PORTS                                                  NAMES
050f30824fcf   php:5.6-fpm     "docker-php-entrypoi…"   3 months ago     Up 3 months               0.0.0.0:9099->9000/tcp, [::]:9099->9000/tcp            php5.6-fpm
d0c24f5527cb   redis           "docker-entrypoint.s…"   13 months ago    Up 3 months               0.0.0.0:6389->6379/tcp, [::]:6389->6379/tcp            redis-ml
ffd9adc61ce2   mysql:8.0       "docker-entrypoint.s…"   17 months ago    Up 5 months               0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp   mysql
4ec122aeda86   qdrant/qdrant   "./entrypoint.sh"        18 months ago    Up 5 months               0.0.0.0:6333->6333/tcp, :::6333->6333/tcp, 6334/tcp    qdrant_container
```

Set `REDIS_URI` and `DATABASE_URL` in `.env`

```
REDIS_URI=redis://:[password]@redis-ml:6379/2

DATABASE_URL=mysql+pymysql://[user_name]:[password]@mysql:3307/crypto_portfolio
```

### Build agent image

```shell

cd musseai-agent

make build
```

### Start service in Docker

```shell
sudo docker-compose -f docker-compose-test.yaml up -d
```

### Shutdown

```shell
sudo docker-compose -f docker-compose-test.yaml down
```

### Show logs

```shell
sudo docker-compose logs -f
```