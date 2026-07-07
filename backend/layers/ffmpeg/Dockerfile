FROM public.ecr.aws/lambda/python:3.12

# Install FFmpeg static build for Amazon Linux 2023 (x86_64)
RUN dnf install -y xz tar && \
    curl -L https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz -o /tmp/ffmpeg.tar.xz && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp && \
    mkdir -p /opt/bin && \
    cp /tmp/ffmpeg-*-amd64-static/ffmpeg /opt/bin/ffmpeg && \
    cp /tmp/ffmpeg-*-amd64-static/ffprobe /opt/bin/ffprobe && \
    chmod +x /opt/bin/ffmpeg /opt/bin/ffprobe && \
    rm -rf /tmp/ffmpeg*
