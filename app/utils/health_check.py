"""
Health check and monitoring service
"""
import asyncio
import logging
import psutil
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health status"""
    service: str
    status: str  # 'healthy', 'warning', 'critical'
    message: str
    timestamp: datetime
    details: Optional[Dict] = None


class HealthChecker:
    """Health checker"""

    def __init__(self):
        self.checks: Dict[str, callable] = {}
        self.last_results: Dict[str, HealthStatus] = {}

    def register_check(self, name: str, check_func: callable):
        """Register health check"""
        self.checks[name] = check_func
        logger.info(f"Registered health check: {name}")

    async def run_all_checks(self) -> List[HealthStatus]:
        """Run all health checks"""
        results = []

        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                if not isinstance(result, HealthStatus):
                    result = HealthStatus(
                        service=name,
                        status='critical',
                        message=f"Invalid health check result for {name}",
                        timestamp=datetime.now()
                    )
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                result = HealthStatus(
                    service=name,
                    status='critical',
                    message=f"Health check failed: {str(e)}",
                    timestamp=datetime.now()
                )

            results.append(result)
            self.last_results[name] = result

        return results

    async def get_system_health(self) -> HealthStatus:
        """System resource health check"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            # Evaluate health status
            status = 'healthy'
            warnings = []

            if cpu_percent > 80:
                status = 'warning'
                warnings.append(f"High CPU usage: {cpu_percent}%")

            if memory_percent > 85:
                status = 'critical' if memory_percent > 95 else 'warning'
                warnings.append(f"High memory usage: {memory_percent}%")

            if disk_percent > 90:
                status = 'critical' if disk_percent > 95 else 'warning'
                warnings.append(f"High disk usage: {disk_percent}%")

            message = '; '.join(warnings) if warnings else "System resources normal"

            return HealthStatus(
                service='system',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details={
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_percent,
                    'disk_percent': disk_percent,
                    'memory_available_gb': round(memory.available / (1024 ** 3), 2)
                }
            )

        except Exception as e:
            return HealthStatus(
                service='system',
                status='critical',
                message=f"System health check failed: {str(e)}",
                timestamp=datetime.now()
            )

    async def check_websocket_connections(self) -> HealthStatus:
        """WebSocket connection health check"""
        try:
            from ..websocket.connection_manager import connection_manager

            active_connections = len(connection_manager.active_connections)
            call_connections = len(connection_manager.call_connections)
            log_connections = len(connection_manager.log_connections)

            total_connections = active_connections + call_connections + log_connections

            status = 'healthy'
            message = f"WebSocket connections: {total_connections} active"

            if total_connections > 100:
                status = 'warning'
                message += " (high connection count)"
            elif total_connections > 200:
                status = 'critical'
                message += " (very high connection count)"

            return HealthStatus(
                service='websocket',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details={
                    'active_connections': active_connections,
                    'call_connections': call_connections,
                    'log_connections': log_connections,
                    'total_connections': total_connections
                }
            )

        except Exception as e:
            return HealthStatus(
                service='websocket',
                status='critical',
                message=f"WebSocket health check failed: {str(e)}",
                timestamp=datetime.now()
            )

    async def check_openai_connection(self) -> HealthStatus:
        """OpenAI connection health check"""
        try:
            from ..services.session_manager import session_manager

            # Check active sessions
            active_sessions = len(session_manager.sessions)

            status = 'healthy'
            message = f"OpenAI sessions: {active_sessions} active"

            return HealthStatus(
                service='openai',
                status=status,
                message=message,
                timestamp=datetime.now(),
                details={
                    'active_sessions': active_sessions
                }
            )

        except Exception as e:
            return HealthStatus(
                service='openai',
                status='critical',
                message=f"OpenAI health check failed: {str(e)}",
                timestamp=datetime.now()
            )


# Global health checker
health_checker = HealthChecker()

# Register default health checks
health_checker.register_check('system', health_checker.get_system_health)
health_checker.register_check('websocket', health_checker.check_websocket_connections)
health_checker.register_check('openai', health_checker.check_openai_connection)
