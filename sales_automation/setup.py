from setuptools import setup, find_packages
with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")
setup(
	name="sales_automation",
	version="0.0.1",
	description="Sales Workflow Automation App",
	author="Nexgen ERP",
	author_email="info@nexgenerptechnologies.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
