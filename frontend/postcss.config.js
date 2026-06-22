find frontend -name "*.js" -o -name "*.css" -o -name "*.ts" | xargs wc -c | sort -n | head -20
