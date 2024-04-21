import setuptools

setuptools.setup(
    name="streamlit_multipage",
    version="0.0.21",
    description="A small package that allows you to create multi page streamlit apps",
    packages=['streamlit_multipage'],
    python_requires=">=3.6",
    install_requires=[
        # public dependencies
        'streamlit>=1.30.0'
    ]
)
