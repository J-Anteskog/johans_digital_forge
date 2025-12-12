# Johan's Digital Forge

A modern, professional portfolio and service website built with Django, showcasing web development services and projects.

## 🌐 Live Site

[Visit Johan's Digital Forge](https://www.johans-digital-forge.se/)

## 📋 About

Johan's Digital Forge is a full-stack web application designed to present professional services, portfolio projects, and facilitate client communication. The platform demonstrates modern web development practices and serves as both a business tool and a showcase of technical capabilities.

## ✨ Features

- **Portfolio Showcase**: Dynamic display of completed projects with detailed descriptions
- **Service Listings**: Comprehensive overview of offered services
- **Contact System**: Integrated contact form for client inquiries
- **Admin Dashboard**: Custom admin interface for content management
- **Responsive Design**: Fully responsive layout optimized for all devices
- **Media Management**: Integrated media handling for images and assets

## 🛠️ Tech Stack

**Backend:**
- Django (Python web framework)
- SQLite/PostgreSQL database
- Django Admin (custom interface)

**Frontend:**
- HTML5 / CSS3 / JavaScript
- Responsive design principles
- Modern UI/UX patterns

**Deployment:**
- Static files management
- Production-ready configuration

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/J-Anteskog/johans_digital_forge.git
   cd johans_digital_forge
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=True
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser (for admin access)**
   ```bash
   python manage.py createsuperuser
   ```

7. **Collect static files**
   ```bash
   python manage.py collectstatic
   ```

8. **Run development server**
   ```bash
   python manage.py runserver
   ```

Visit `http://localhost:8000` to view the site.

## 📁 Project Structure

```
johans_digital_forge/
├── contact/              # Contact form and inquiry handling
├── custom_admin/         # Custom admin interface
├── home/                 # Homepage and landing pages
├── portfolio/            # Portfolio projects showcase
├── service/              # Service offerings and descriptions
├── media/                # User-uploaded media files
├── static/               # Static assets (CSS, JS, images)
├── staticfiles/          # Collected static files for production
├── templates/            # HTML templates
├── johans_digital_forge/ # Main project configuration
├── manage.py             # Django management script
├── requirements.txt      # Python dependencies
└── data.json             # Fixture data (if applicable)
```

## 🎨 Key Applications

### Portfolio
Manages and displays completed projects with:
- Project descriptions
- Technologies used
- Project images
- Links to live demos or repositories

### Service
Showcases offered services including:
- Web development
- Consulting
- Custom solutions
- Technical specifications

### Contact
Handles client communication:
- Contact form submission
- Inquiry management
- Email notifications

### Custom Admin
Enhanced Django admin with:
- Improved UI/UX
- Custom workflows
- Efficient content management

## 🔒 Security Notes

- Never commit `.env` files or sensitive credentials
- SECRET_KEY should be kept private and rotated regularly
- Use environment variables for all sensitive configuration
- Ensure DEBUG is set to False in production

## 📝 Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
SECRET_KEY=your-django-secret-key
DEBUG=False  # Set to True only for development
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=your-database-url  # If using PostgreSQL
EMAIL_HOST=smtp.gmail.com  # Email configuration
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-email-password
```

## 🚢 Deployment

This project is deployment-ready for platforms like:
- Heroku
- DigitalOcean
- Railway
- PythonAnywhere
- AWS/Azure/GCP

Ensure you:
1. Set all environment variables
2. Use a production-grade database (PostgreSQL recommended)
3. Configure static file serving
4. Enable HTTPS
5. Set up proper DNS configuration

## 📧 Contact

**Johan Anteskog**

- GitHub: [@J-Anteskog](https://github.com/J-Anteskog)
- Website: [Johan's Digital Forge](https://www.johans-digital-forge.se/)
- Email: [info@johans-digital-forge.se]

## 📄 License

This project is proprietary software. All rights reserved.

*For inquiries about using this code or collaborating, please contact via the website.*

## 🤝 Contributing

This is a personal/business project, but suggestions and feedback are welcome! Feel free to:
- Open an issue for bug reports
- Submit feature suggestions
- Reach out for collaboration opportunities

## 🙏 Acknowledgments

- Built with Django and modern web technologies
- Inspired by contemporary web design principles
- Developed with passion for clean code and user experience

---

**Made with ❤️ in Sweden** 🇸🇪
