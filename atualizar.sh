#! /bin/bash

cd ~/chatbotServicos
source ./chatbotVenv/bin/activate
python -c "import novoMetodo; novoMetodo.atualizarJson();" >> log
deactivate

