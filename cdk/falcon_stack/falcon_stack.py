from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_iam as iam,
    CfnOutput,
)

class FalconStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        openai_key: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Use default VPC
        vpc = ec2.Vpc.from_lookup(self, "Vpc", is_default=True)

        # Security Group
        sg = ec2.SecurityGroup(
            self,
            "FalconSG",
            vpc=vpc,
            description="Security group for Falcon University stack",
            allow_all_outbound=True,
        )

        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP",
        )

        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS",
        )

        # Allow SSH from current IP only (safer)
        sg.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(22),
            description="Allow SSH",
        )

        # IAM Role for EC2
        role = iam.Role(
            self,
            "FalconEc2Role",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
        )

        # Allow SSM access for debugging (optional but handy)
        role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")
        )

        # AMI: Amazon Linux 2023
        ami = ec2.MachineImage.latest_amazon_linux2023()

        # Root volume 30 GB gp3
        block_devices = [
            ec2.BlockDevice(
                device_name="/dev/xvda",
                volume=ec2.BlockDeviceVolume.ebs(
                    volume_size=30,
                    volume_type=ec2.EbsDeviceVolumeType.GP3,
                    delete_on_termination=True,
                ),
            )
        ]

        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            # Update and install Docker, Git
            "dnf update -y",
            "dnf install -y docker git",
            "systemctl enable docker",
            "systemctl start docker",
            "usermod -aG docker ec2-user",
            # Docker Compose plugin
            'DOCKER_CONFIG=${DOCKER_CONFIG:-/usr/local/lib/docker}',
            'mkdir -p $DOCKER_CONFIG/cli-plugins',
            'curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o $DOCKER_CONFIG/cli-plugins/docker-compose',
            'chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose',
            'ln -s $DOCKER_CONFIG/cli-plugins/docker-compose /usr/local/bin/docker-compose',
            # Swap
            "fallocate -l 4G /swapfile",
            "chmod 600 /swapfile",
            "mkswap /swapfile",
            "swapon /swapfile",
            "echo '/swapfile none swap sw 0 0' >> /etc/fstab",
            # Clone repo
            "mkdir -p /opt/falcon",
            "git clone https://github.com/bhanotr/falcon.git /opt/falcon || true",
            # Write .env
            f"cat > /opt/falcon/.env << 'EOF'\nOPENAI_API_KEY={openai_key}\nSECRET_KEY=supersecretkey-{openai_key[:8]}\nEOF",
            # Start containers
            "cd /opt/falcon && docker compose up -d --build",
        )

        instance = ec2.Instance(
            self,
            "FalconInstance",
            instance_type=ec2.InstanceType("c7i-flex.large"),
            machine_image=ami,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=sg,
            role=role,
            block_devices=block_devices,
            user_data=user_data,
            associate_public_ip_address=True,
        )

        CfnOutput(self, "InstancePublicIp", value=instance.instance_public_ip)
        CfnOutput(self, "InstanceId", value=instance.instance_id)
