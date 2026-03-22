# Workshop UI Package

This package contains the pre-built UI components for the "Everyday Productivity Accelerators" workshop.

## Quick Start

1. **Extract the package:**
   ```bash
   unzip workshop-ui-package.zip
   cd ui
   ```

2. **Backend Setup:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup:**
   ```bash
   cd ../frontend
   npm install
   ```

4. **Start the Application:**
   ```bash
   cd ..
   ./start.sh
   ```

5. **Access the Application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Workshop Structure

- `backend/` - Python FastAPI backend with Strands Agents
- `frontend/` - React frontend application
- `start.sh` - Convenience script to start both services

## Requirements

- Python 3.11+
- Node.js 18+
- AWS credentials configured for Bedrock access

## Support

If you encounter issues during the workshop, please ask your instructor for assistance.

---
*Built for AWS Workshop*
