#!/bin/bash
gunicorn -b 0.0.0.0:9001 app:app