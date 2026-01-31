# Contributing to PiFM

Thank you for your interest in contributing to PiFM!

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for project layout and GitHub workflow.

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the backend service:
   ```bash
   python backend/fm_receiver.py
   ```

4. Access the web interface at `http://localhost:8080`

## Testing

Before submitting changes, please test:

- RTL-SDR detection
- FM streaming at various frequencies
- Web interface functionality
- Preset management
- Service restart behavior

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add comments for complex logic
- Keep functions focused and small

## Submitting Changes

1. Create a branch for your changes
2. Make your changes
3. Test thoroughly
4. Submit a pull request with a clear description

## Hardware Testing

If possible, test on actual Raspberry Pi hardware with RTL-SDR dongle.
