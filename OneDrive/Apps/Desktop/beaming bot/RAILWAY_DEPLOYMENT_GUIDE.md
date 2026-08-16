# 🚀 Railway.app Deployment Guide

## **Step-by-Step Instructions**

### **1. Create Railway Account**
1. Go to [railway.app](https://railway.app)
2. Click "Start for Free"
3. Sign up with GitHub (recommended)
4. Authorize Railway to access your GitHub repositories

### **2. Create New Project**
1. Click "New Project" in Railway dashboard
2. Select "Deploy from GitHub repo"
3. Choose your repository: `asdasdsd672/bezmerz-bot`
4. Click "Import"

### **3. Configure Project Settings**

#### **Build Settings**
- **Build Command**: Leave empty (Railway will auto-detect)
- **Start Command**: `python CodeX.py`

#### **Environment Variables** (Required)
Add these in the "Variables" tab:

```
DISCORD_TOKEN=your_discord_bot_token_here
```

**Optional Variables:**
```
DATABASE_URL=your_database_url_if_using_external_db
WEB_SECRET_KEY=your_web_dashboard_secret_key
OPENAI_API_KEY=your_openai_api_key_if_using_ai_features
```

### **4. Deploy**
1. Click "Deploy" button
2. Railway will automatically:
   - Install dependencies from requirements.txt
   - Set up Python environment
   - Start your bot using the Procfile
3. Wait for deployment to complete (usually 2-5 minutes)

### **5. Monitor Your Bot**
- Check the "Logs" tab to see bot activity
- Monitor resource usage in "Metrics" tab
- Set up alerts in "Alerts" tab

## **Troubleshooting**

### **Bot Won't Start**
- Check logs for error messages
- Verify DISCORD_TOKEN is correct
- Ensure CodeX.py is in the root directory

### **Connection Issues**
- Check if DISCORD_TOKEN has proper intents
- Verify bot is in the correct servers
- Check Railway status page for outages

### **Database Issues**
- For SQLite: Ensure db/ directory exists
- For external database: Check DATABASE_URL
- Verify database permissions

## **Advanced Configuration**

### **Custom Domain**
1. Go to "Settings" → "Domains"
2. Add your custom domain
3. Configure DNS records

### **Auto-Deploy**
1. Go to "Settings" → "Git"
2. Enable "Auto-deploy on push"
3. Select branch to watch (usually master)

### **Scaling**
1. Go to "Settings" → "Scale"
2. Adjust CPU/RAM as needed
3. Note: Free tier has limits

## **Cost & Limits**

### **Free Tier**
- $5 free credit per month
- 512MB RAM
- 0.5 vCPU
- 1GB storage
- 500 hours of execution time

### **Paid Plans**
- Hobby: $5/month
- Pro: $20/month
- Custom: Enterprise pricing

## **Best Practices**

### **Keep Your Bot Running**
- Use UptimeRobot to ping your bot
- Set up proper error handling
- Monitor logs regularly

### **Optimize Performance**
- Use efficient database queries
- Implement caching where possible
- Limit resource-intensive operations

### **Security**
- Never commit sensitive data
- Use environment variables for secrets
- Rotate tokens regularly
- Enable 2FA on Railway account

## **Useful Railway Commands**

### **Railway CLI**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# View logs
railway logs

# Open in browser
railway open
```

### **Common Issues**

**"Module not found" error:**
- Check requirements.txt has all dependencies
- Ensure Python version compatibility

**"Permission denied" error:**
- Check file permissions in repository
- Verify Procfile is correct

**"Out of memory" error:**
- Upgrade to paid plan
- Optimize bot code
- Reduce memory usage

## **Web Dashboard Deployment**

If you want to deploy the web dashboard alongside the bot:

### **Option 1: Separate Service**
1. Create new Railway service
2. Set start command: `python web_dashboard.py`
3. Add WEB_SECRET_KEY environment variable
4. Deploy separately

### **Option 2: Combined Service**
1. Modify CodeX.py to run both bot and web dashboard
2. Use threading or async to run both
3. Single deployment for both services

## **Maintenance**

### **Regular Updates**
1. Update dependencies in requirements.txt
2. Test locally before deploying
3. Push to GitHub for auto-deploy

### **Monitoring**
1. Check logs daily
2. Monitor resource usage
3. Set up alerts for downtime

### **Backups**
1. Export database regularly
2. Backup configuration files
3. Keep local copy of code

## **Support**

- **Railway Documentation**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **GitHub Issues**: https://github.com/railwayapp/cli/issues

Your bot is now ready for Railway deployment! 🚀
