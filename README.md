# Sales Tracker

A modern, playful web application for sales tracking and analytics with an interactive login experience.

## Features

- 📊 **Sales Analytics Dashboard** - Track and visualize sales performance
- 👥 **User Management** - Multi-level permission system for team collaboration
- 📈 **Data Entry & Export** - Easy sales data input with Excel export capabilities
- 🎮 **Interactive Login** - Unique, playful login experience with cursor-evasive Sign In button
- 🔒 **Secure Authentication** - Session-based authentication with password hashing
- 📱 **Responsive Design** - Works seamlessly on desktop and mobile devices

## Quick Start

```bash
docker run -d \
  -p 5000:5000 \
  -v sales-data:/app/data \
  -v sales-uploads:/app/uploads \
  --name sales-tracker \
  tebwritescode/sales-tracker:latest
```

Access the application at `http://localhost:5000`

## Default Credentials

- **Username:** `admin`
- **Password:** `admin`

⚠️ **Important:** Change the default credentials immediately after first login!

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for session encryption | `dev-key-change-in-production` |
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///data/sales_tracker.db` |
| `SQLALCHEMY_TRACK_MODIFICATIONS` | Track SQLAlchemy modifications | `False` |
| `UPLOAD_FOLDER` | Directory for file uploads | `uploads` |
| `MAX_CONTENT_LENGTH` | Maximum upload file size (bytes) | `16777216` (16MB) |
| `FLASK_ENV` | Flask environment | `production` |

## Docker Compose Example

```yaml
version: '3.8'

services:
  sales-tracker:
    image: tebwritescode/sales-tracker:latest
    container_name: sales-tracker
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=your-secret-key-here
      - DATABASE_URL=sqlite:///data/sales_tracker.db
    volumes:
      - sales-data:/app/data
      - sales-uploads:/app/uploads
    restart: unless-stopped

volumes:
  sales-data:
  sales-uploads:
```

## Volumes

| Path | Description |
|------|-------------|
| `/app/data` | Database storage location |
| `/app/uploads` | User uploaded files |

## Networking

The container exposes port `5000` by default. For production deployments, it's recommended to use a reverse proxy like Nginx or Traefik.

### Nginx Reverse Proxy Example

```nginx
server {
    listen 80;
    server_name sales.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Interactive Login Experience

This application features a unique, playful login interface where:
- The login box expands when you approach it
- The Sign In button actively evades your cursor until you fill in both username and password fields
- Provides an engaging user experience while maintaining security

## User Permission Levels

1. **Admin (Level 4)** - Full system access
2. **Manager (Level 3)** - User management and data oversight
3. **Supervisor (Level 2)** - Team data management
4. **User (Level 1)** - Basic data entry

## Health Check

The container includes a built-in health check that verifies the application is responding:

```bash
docker inspect --format='{{.State.Health.Status}}' sales-tracker
```

## Backup & Restore

### Backup Database
```bash
docker exec sales-tracker sqlite3 /app/data/sales_tracker.db ".backup /tmp/backup.db"
docker cp sales-tracker:/tmp/backup.db ./backup.db
```

### Restore Database
```bash
docker cp ./backup.db sales-tracker:/tmp/backup.db
docker exec sales-tracker sqlite3 /app/data/sales_tracker.db ".restore /tmp/backup.db"
```

## Supported Architectures

- `linux/amd64` - Standard x86-64
- `linux/arm64` - ARM 64-bit (Apple Silicon, AWS Graviton)

## Features Not Yet Implemented

The following features show placeholder messages and are not yet functional:

### Management Page ('/management')
- **Settings** - "Settings" button (shows placeholder alert)
- **Payroll Reports** - "Generate Payroll Report" button (shows placeholder alert)

### System Settings ('/settings')
- **System Settings Page** - In the menu bar under System > System Settings the link leads to a 404 page

The UI elements are in place but the backend functionality needs to be implemented.

## Security Considerations

1. **Change default credentials** immediately after deployment
2. **Use strong SECRET_KEY** in production
3. **Enable HTTPS** with a reverse proxy
4. **Regular backups** of the database
5. **Update regularly** for security patches

## Troubleshooting

### Container won't start
```bash
docker logs sales-tracker
```

### Reset admin password
```bash
docker exec -it sales-tracker python -c "
from app import app, db, User
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    if admin:
        admin.set_password('new_password')
        db.session.commit()
        print('Password reset successfully')
"
```

### Database initialization issues
```bash
docker exec -it sales-tracker python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database initialized')
"
```

## Source Code

- **GitHub:** [tebwritescode/sales-tracker](https://github.com/tebwritescode/sales-tracker)
- **Docker Hub:** [tebwritescode/sales-tracker](https://hub.docker.com/r/tebwritescode/sales-tracker)

## License

MIT License

## Author

**tebwritescode**  
Website: [https://tebwrites.code](https://tebwrites.code)

## Version

Current Version: `1.2.0`

---

*For issues, feature requests, or contributions, please visit the [GitHub repository](https://github.com/tebwritescode/sales-tracker).*
