FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY avatar_lambda.py process_sprite.py ${LAMBDA_TASK_ROOT}/

CMD ["avatar_lambda.handler"]
