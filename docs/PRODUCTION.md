# TerryFox LIMS - Production Setup (Robust)

This document provides instructions for deploying TerryFox LIMS in robust production mode with Gunicorn, systemd, and automatic monitoring.

## 🚀 Robust Production Architecture

The production system now uses:
- **Gunicorn**: Stable and performant production WSGI server
- **systemd**: Service management with automatic restart
- **Watchdog**: Automatic monitoring and error recovery
- **Centralized logging**: Complete logging infrastructure
- **Native SSL**: Integrated HTTPS support with certificates

## Prerequisites

- Python 3.8+ (via Conda environment `django`)
- Django and required packages (see requirements.txt)
- **Gunicorn** installed in the Conda environment
- Root access (sudo) for:
  - Using port 443 (HTTPS)
  - Managing systemd services
  - Creating log directories
- SSL certificates in `/root/ssl/`:
  - `/root/ssl/terryfox.crt`
  - `/root/ssl/terryfox.key`

## 🔧 Installation and Configuration

### 1. Gunicorn Installation

```bash
# Activate Conda environment
source /home/hadriengt/miniconda/etc/profile.d/conda.sh
conda activate django

# Install Gunicorn
pip install gunicorn
```

### 2. SSL Certificate Verification

```bash
# Verify that certificates exist
sudo ls -la /root/ssl/
# Should contain: terryfox.crt and terryfox.key
```

### 3. systemd Service Configuration

The systemd service is already configured with:
- Automatic restart on failure
- Resource limits (2GB RAM, 90% CPU)
- Timeout management
- Logging to journald

## 🚀 Service Startup

### Initial Startup

```bash
# Start the service
sudo systemctl start terryfox-lims.service

# Check status
sudo systemctl status terryfox-lims.service

# Enable automatic startup
sudo systemctl enable terryfox-lims.service
```

### Monitoring System Activation

```bash
# Enable watchdog (automatic monitoring)
sudo systemctl enable --now terryfox-lims-watchdog.timer

# Verify that the timer is active
sudo systemctl list-timers terryfox-lims-watchdog.timer
```

## 📊 Application Access

Once the service is started, the application is accessible via:
- **https://10.220.115.67** (access via IP address)
- **https://localhost** (local access only)

**Note**: Your browser will display a security warning due to the self-signed certificate. This is normal and expected - you can safely accept the certificate exception.

## 🔍 Monitoring and Maintenance

### Watchdog System

The monitoring system automatically:
- Checks Gunicorn processes every 5 minutes
- Performs HTTP health checks
- Monitors memory usage
- Restarts the service on failure

### Log Monitoring

```bash
# View real-time service logs
sudo journalctl -u terryfox-lims.service -f

# View watchdog logs
tail -f /var/log/terryfox-lims/watchdog.log

# View access logs
tail -f /var/log/terryfox-lims/access.log

# View error logs
tail -f /var/log/terryfox-lims/error.log
```

### Service Management

Main commands to manage the LIMS service:

```bash
# Check service status
sudo systemctl status terryfox-lims.service

# Restart the service
sudo systemctl restart terryfox-lims.service

# Stop the service
sudo systemctl stop terryfox-lims.service

# Reset the service
sudo systemctl reset-failed terryfox-lims.service
sudo systemctl start terryfox-lims.service
```

## 🔒 Security and Best Practices

### Security Configuration
- ✅ HTTPS mandatory (port 443)
- ✅ SSL certificates configured
- ✅ Security headers enabled
- ✅ Resource limits applied
- ✅ Process isolation

### Recommendations
1. **Monitor regularly** error logs
2. **Backup** the database regularly
3. **Update** SSL certificates before expiration
4. **Test** recovery procedures
5. **Document** any configuration changes

## 📈 Architecture Advantages

| Aspect | Legacy System | New Robust System |
|--------|---------------|-------------------|
| Server | runserver_plus (dev) | Gunicorn (production) |
| Supervision | Basic bash script | systemd + watchdog |
| Recovery | Manual | Automatic |
| Logs | Scattered | Centralized |
| Monitoring | None | Continuous monitoring |
| Stability | Unstable | High availability |

## 🆘 Support and Contact

In case of persistent issues:
1. Check detailed logs
2. Review troubleshooting documentation
3. Contact the development team with:
   - Complete error logs
   - Commands executed
   - Problem context

---

**Note**: This configuration completely replaces the old system based on `start_production_debug.sh`. The new system is more robust, more secure, and requires less manual maintenance.

## 🔧 Troubleshooting

### Common Issues

#### Service Won't Start
```bash
# Check service status
sudo systemctl status terryfox-lims.service

# View detailed logs
sudo journalctl -u terryfox-lims.service --no-pager

# Check SSL certificates
sudo ls -la /root/ssl/
```

#### Connection Issues
```bash
# Test local connection
curl -k -I https://localhost:443/

# Test network connection
curl -k -I https://10.220.115.67:443/

# Check if port is listening
sudo netstat -tlnp | grep :443
```

#### High Memory Usage
```bash
# Check memory usage
ps aux | grep gunicorn

# Restart service if needed
sudo systemctl restart terryfox-lims.service
```

### Log Locations
- **Service logs**: `sudo journalctl -u terryfox-lims.service`
- **Access logs**: `/var/log/terryfox-lims/access.log`
- **Error logs**: `/var/log/terryfox-lims/error.log`
- **Watchdog logs**: `/var/log/terryfox-lims/watchdog.log`

### Emergency Recovery
```bash
# Stop all services
sudo systemctl stop terryfox-lims.service
sudo systemctl stop terryfox-lims-watchdog.timer

# Reset and restart
sudo systemctl reset-failed terryfox-lims.service
sudo systemctl start terryfox-lims.service
sudo systemctl start terryfox-lims-watchdog.timer
``` 