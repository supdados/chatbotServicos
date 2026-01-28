#! /bin/bash

cd ~/chatbotServicos
source ./chatbotVenv/bin/activate
python -u -c "import novoMetodo; novoMetodo.atualizarJson();" >> log
deactivate

