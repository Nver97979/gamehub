# GameHub 🎮

A Flask web application for browsing and managing games with user authentication and admin dashboard.

## Features

- 🎮 Browse 100 games across multiple categories
- 👤 User registration and login
- 🔐 Password hashing with Werkzeug
- 📝 Admin panel for game management
- 🖼️ Image uploads for game covers
- 🔒 Temporary game closure functionality
- 🌐 Fully responsive design
- 🇦🇲 Armenian language interface

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Nver97979/gamehub.git
cd gamehub

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
```

### Default Admin Credentials

- **Email**: `admin@gamehub.local`
- **Password**: `Admin123!`

### Access the Application

- **Website**: http://localhost:5000
- **Admin Panel**: http://localhost:5000/admin

## API Endpoints

### Games
- `GET /api/games` - Get all games
- `POST /api/admin/games` - Add a new game (admin only)
- `PUT /api/admin/games/<id>` - Edit a game (admin only)
- `DELETE /api/admin/games/<id>` - Delete a game (admin only)
- `POST /api/admin/games/<id>/close` - Close a game (admin only)
- `POST /api/admin/games/<id>/open` - Open a closed game (admin only)

### Authentication
- `POST /api/register` - Register a new user
- `POST /api/login` - Login user
- `GET /api/me` - Get current user info

## Database

SQLite database with two tables:
- **users** - User accounts and admin privileges
- **games** - Game catalog with metadata

## Categories

- Action
- Adventure
- Racing
- Sports
- RPG
- Sandbox

## File Structure

```
gamehub/
├── app.py              # Main Flask application
├── gamehub.db          # SQLite database (auto-created)
├── uploads/            # Game image uploads
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Technologies

- **Backend**: Flask 2.3.2
- **Database**: SQLite3
- **Security**: Werkzeug password hashing
- **Frontend**: Vanilla JavaScript, HTML5, CSS3

## License

MIT License
