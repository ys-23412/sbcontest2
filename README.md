Scrapping sites and downloads information to upload to the apis, bcbid under progress.


For the proxy used, we setup a free google cloud platform and the following instructions

To set up a simple authenticated proxy on Google Cloud Platform (GCP) for use with Chrome, the most reliable and "lightweight" method is deploying a **Squid Proxy** on a small Compute Engine instance. My plan is turn off the instance if it gets blocked and then turn it back on (getting a new ip address in the process), also swap between linux, windows and mac osx.

### **Phase 1: Create the GCP Instance**

1.  Go to the [GCP Console](https://console.cloud.google.com/) and navigate to **Compute Engine \> VM Instances**.
2.  Click **Create Instance**.
3.  **Machine configuration:** Select **e2-micro** (this is usually enough for a personal proxy).
4.  **Boot disk:** Choose **Ubuntu 22.04 LTS** or **24.04 LTS**.
5.  **Firewall:** Check **Allow HTTP traffic** (we will manually open the proxy port later).
6.  Click **Create**.

-----

### **Phase 2: Install and Configure Squid**

Once the VM is running, click the **SSH** button next to it to open a terminal. Run the following commands:

#### **1. Install Squid and Utilities**

```bash
sudo apt-get update
sudo apt-get install squid apache2-utils -y
```

#### **2. Create the Password File**

Replace `your_username` with the name you want to use. You will be prompted to enter and confirm a password.

```bash
sudo htpasswd -c /etc/squid/passwords your_username
```

#### **3. Configure Squid for Authentication**

Open the config file:

```bash
sudo nano /etc/squid/squid.conf
```

Scroll to the very top and paste these lines **above** all other rules:

```text
auth_param basic program /usr/lib/squid/basic_ncsa_auth /etc/squid/passwords
auth_param basic realm Squid proxy
auth_param basic credentialsttl 24 hours
auth_param basic casesensitive off

acl authenticated proxy_auth REQUIRED
http_access allow authenticated
http_port 3128
```

*Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save and exit.*

#### **4. Restart Squid**

```bash
sudo systemctl restart squid
```

-----

### **Phase 3: Open the Firewall in GCP**

By default, GCP blocks port `3128`. You must open it:

1.  In the GCP Console, search for **VPC Network \> Firewall**.
2.  Click **Create Firewall Rule**.
3.  **Name:** `allow-proxy`
4.  **Targets:** `All instances in the network`
5.  **Source IPv4 range:** `0.0.0.0/0` (Note: For better security, use your own home/office IP instead).
6.  **Protocols and ports:** Check **TCP** and enter `3128`.
7.  Click **Create**.

-----

### **Phase 4: Connect with Chrome with pydoll**

use the following format user:pass@external_ip_address:port in pydoll and save as a variable PROXY_URL_WITH_PASS