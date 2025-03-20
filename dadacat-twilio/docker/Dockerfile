FROM public.ecr.aws/lambda/python:3.12

# Set up environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy Lambda functions
COPY handler.py ${LAMBDA_TASK_ROOT}/
COPY processor.py ${LAMBDA_TASK_ROOT}/

# Copy source code
COPY src ${LAMBDA_TASK_ROOT}/src/
COPY dada_agents ${LAMBDA_TASK_ROOT}/dada_agents/

# Command can be overridden by providing a different command in the template directly
CMD ["handler.lambda_handler"]
