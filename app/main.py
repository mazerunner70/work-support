"""
Main FastAPI application for the Work Support Python Server.
"""
import logging
import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import config_manager
from app.services.database_service import db_service
from app.api.routes import router
from app.api.mcp_routes import mcp_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not config_manager.settings.server_debug else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Enable SQLAlchemy SQL logging
if config_manager.settings.server_debug:
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.INFO)

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    """Log all incoming HTTP requests with timing."""
    start_time = time.time()
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Call the endpoint
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log the request
    logger.info(
        f"HTTP {request.method} {request.url.path}"
        f"{('?' + str(request.url.query)) if request.url.query else ''} "
        f"- {response.status_code} - {duration:.3f}s - {client_ip}"
    )
    
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting Work Support Python Server...")

    try:
        # Perform startup recovery and check if reload is needed
        recovery_performed, reload_needed = db_service.perform_startup_recovery()
        if recovery_performed:
            logger.warning("Startup recovery was performed - check logs for details")

        # Initialize issue types in database if needed
        await initialize_issue_types()

        # Trigger reload if needed
        if reload_needed:
            logger.info("🚀 AUTOMATIC RELOAD - Triggering due to reload interval...")
            reload_record = db_service.create_reload_tracking(
                source='automatic',
                triggered_by='system-startup'
            )
            if reload_record:
                auto_reload_start_time = time.time()
                logger.info(f"⚡ PROCESSING - Automatic reload ID {reload_record.id} starting data harvesting... - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
                # Perform actual data harvesting
                try:
                    from app.services.harvest_service import harvest_service
                    records_processed, status_message = await harvest_service.perform_full_harvest()
                    db_service.complete_reload(reload_record.id, records_processed)
                    
                    # Calculate automatic reload duration
                    auto_reload_duration = time.time() - auto_reload_start_time
                    auto_reload_duration_str = f"{auto_reload_duration:.2f}s"
                    if auto_reload_duration >= 60:
                        minutes = int(auto_reload_duration // 60)
                        seconds = auto_reload_duration % 60
                        auto_reload_duration_str = f"{minutes}m {seconds:.1f}s"
                    
                    logger.info(f"✅ AUTOMATIC RELOAD COMPLETED - {status_message} - Duration: {auto_reload_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
                except Exception as e:
                    # Calculate duration even for failed automatic reloads
                    auto_reload_duration = time.time() - auto_reload_start_time
                    auto_reload_duration_str = f"{auto_reload_duration:.2f}s"
                    if auto_reload_duration >= 60:
                        minutes = int(auto_reload_duration // 60)
                        seconds = auto_reload_duration % 60
                        auto_reload_duration_str = f"{minutes}m {seconds:.1f}s"
                    
                    error_msg = f"Automatic reload failed: {e}"
                    logger.error(f"❌ AUTOMATIC RELOAD FAILED - {error_msg} - Duration: {auto_reload_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
                    db_service.fail_reload(reload_record.id, error_msg)
            else:
                logger.error("❌ ERROR - Failed to create automatic reload tracking")

        # Start the scheduler for automated harvesting
        from app.services.scheduler_service import scheduler_service
        scheduler_service.start_scheduler()
        
        logger.info("Server startup completed successfully")

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Work Support Python Server...")
    
    # Stop the scheduler
    try:
        from app.services.scheduler_service import scheduler_service
        scheduler_service.stop_scheduler()
    except Exception as e:
        logger.error(f"Error stopping scheduler during shutdown: {e}")


async def initialize_issue_types():
    """Initialize and sync issue types in the database."""
    try:
        from app.services.issue_type_sync_service import IssueTypeSyncService

        with db_service.get_db_session() as db:
            # Always sync issue types to ensure they're up to date
            IssueTypeSyncService.sync_on_startup(db)

    except Exception as e:
        logger.error(f"Error initializing issue types: {e}")
        raise


# Create FastAPI application
app = FastAPI(
    title="Work Support Python Server",
    description="Data harvesting and API service for GitHub and Jira integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add HTTP request logging middleware
app.middleware("http")(log_requests)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Include MCP-specific routes
app.include_router(mcp_router)

# Global exception handler


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config_manager.settings.server_host,
        port=config_manager.settings.server_port,
        reload=config_manager.settings.server_debug,
        log_level="debug" if config_manager.settings.server_debug else "info"
    )
