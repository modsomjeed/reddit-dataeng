DIAGRAMS_DIR := docs/architecture/diagrams

.PHONY: diagrams
diagrams: ## Render every PlantUML diagram to SVG
	docker run --rm -v "$(CURDIR)/$(DIAGRAMS_DIR)":/data plantuml/plantuml:latest -tsvg "/data/*.puml"
