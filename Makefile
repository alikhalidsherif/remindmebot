.PHONY: help build up down restart logs status clean check test deploy update backup

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check: ## Run pre-deployment checks
	@echo "Running pre-deployment checks..."
	@./pre-deploy-check.sh

build: ## Build Docker image
	@echo "Building Docker image..."
	@docker-compose build

up: ## Start the bot
	@echo "Starting bot..."
	@docker-compose up -d
	@echo "Bot started! Use 'make logs' to view logs."

down: ## Stop the bot
	@echo "Stopping bot..."
	@docker-compose down

restart: ## Restart the bot
	@echo "Restarting bot..."
	@docker-compose restart
	@echo "Bot restarted!"

logs: ## View bot logs (follow mode)
	@docker-compose logs -f bot

status: ## Check bot status
	@docker-compose ps
	@echo ""
	@docker stats telegram-reminder-bot --no-stream 2>/dev/null || echo "Container not running"

clean: ## Remove containers, volumes, and images
	@echo "Cleaning up..."
	@docker-compose down -v
	@docker rmi telegram-reminder-bot:latest 2>/dev/null || true
	@echo "Cleanup complete!"

test: ## Run tests
	@echo "Running tests..."
	@docker-compose run --rm bot pytest -v

deploy: check build up ## Full deployment (check, build, and start)
	@echo ""
	@echo "✅ Deployment complete!"
	@echo "View logs: make logs"
	@echo "Check status: make status"

update: ## Update bot (pull, rebuild, restart)
	@echo "Updating bot..."
	@git pull origin main
	@docker-compose down
	@docker-compose build --no-cache
	@docker-compose up -d
	@echo ""
	@echo "✅ Update complete!"
	@echo "View logs: make logs"

backup: ## Backup database
	@echo "Backing up database..."
	@mkdir -p backups
	@cp ./data/reminders.db ./backups/reminders_$$(date +%Y%m%d_%H%M%S).db 2>/dev/null || echo "No database to backup"
	@echo "Backup complete! Check ./backups directory"

shell: ## Open shell in bot container
	@docker-compose exec bot /bin/sh

validate: ## Validate configuration files
	@echo "Validating configuration..."
	@docker-compose config > /dev/null && echo "✓ docker-compose.yml is valid"
	@python -m py_compile bot/*.py && echo "✓ Python files are valid" || true
