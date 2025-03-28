import torch
import torch.nn.functional as F
import wandb
from tqdm import tqdm
import logging
import torchvision

logger = logging.getLogger(__name__)


def train_epoch(generator, discriminator, optimizer_g, optimizer_d, dataloader, device, config, epoch, global_step):
    generator.train()
    discriminator.train()

    total_g_loss = 0.0
    total_d_loss = 0.0
    n_batches = 0

    progress_bar = tqdm(
        dataloader, desc=f"Epoch {epoch}/{config['epochs']}", unit="batch", leave=False)
    for i, (imgs, labels) in enumerate(progress_bar):
        imgs = imgs.to(device)
        labels = labels.to(device)

        batch_size = imgs.size(0)
        n_batches += 1

        # Ground truths
        valid = torch.ones(batch_size, device=device)
        fake = torch.zeros(batch_size, device=device)

        # -----------------
        #  Train Generator
        # -----------------
        optimizer_g.zero_grad()
        noise = torch.randn(batch_size, config["latent_dim"], 1, 1, device=device)
        gen_imgs = generator(noise, labels)
        g_loss = F.binary_cross_entropy(discriminator(gen_imgs, labels), valid)
        g_loss.backward()
        optimizer_g.step()

        # ---------------------
        #  Train Discriminator
        # ---------------------
        optimizer_d.zero_grad()
        real_loss = F.binary_cross_entropy(discriminator(imgs, labels), valid)
        fake_loss = F.binary_cross_entropy(
            discriminator(gen_imgs.detach(), labels), fake)
        d_loss = (real_loss + fake_loss) / 2
        d_loss.backward()
        optimizer_d.step()

        total_g_loss += g_loss.item()
        total_d_loss += d_loss.item()

        progress_bar.set_postfix(g_loss=g_loss.item(), d_loss=d_loss.item())

        if config.get("log_interval", -1) != -1 and i % config["log_interval"] == 0:
            wandb.log({
                "batch_g_loss": g_loss.item(),
                "batch_d_loss": d_loss.item(),
                "epoch": epoch,
                "batch": i
            }, step=global_step)

        global_step += 1

    # Compute average losses for the epoch
    avg_g_loss = total_g_loss / n_batches
    avg_d_loss = total_d_loss / n_batches
    wandb.log({
        "epoch_avg_g_loss": avg_g_loss,
        "epoch_avg_d_loss": avg_d_loss,
        "epoch": epoch
    }, step=global_step)

    logger.info(
        f"Epoch {epoch} finished: avg_g_loss={avg_g_loss:.4f}, avg_d_loss={avg_d_loss:.4f}")
    return global_step


def evaluate(generator, device, config, step):
    generator.eval()
    with torch.no_grad():
        noise = torch.randn(config["num_eval_samples"],
                            config["latent_dim"], 1, 1, device=device)
        labels = torch.randint(
            0, config["num_classes"], (config["num_eval_samples"],), device=device)
        # Generate images
        gen_imgs = generator(noise, labels)
        grid = torchvision.utils.make_grid(gen_imgs, nrow=4, normalize=True)
        wandb.log({"generated_images": [wandb.Image(
            grid, caption="Generated Images")]}, step=step)
    generator.train()
